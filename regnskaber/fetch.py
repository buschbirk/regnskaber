import csv
import functools
import os
import sys
import tempfile
import time

from datetime import datetime
from multiprocessing import Process, Lock

import elasticsearch
import requests

from elasticsearch import Elasticsearch
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search

from .ioqueue import IOQueueManager

from .unitrefs import UnitHandler
from .regnskab_inserter import drive_regnskab

from . import Session, engine, parse_date, setup_database_connection
from .models import FinancialStatement, Base

ERASE = '\r\x1B[K'
ENCODING = 'UTF-8'

csv.field_size_limit(2**31-1)


def setup_tables():
    Base.metadata.create_all(engine)
    return


class InputRegnskabError(Exception):
    """Exception raised for errors in the raw regnskabs data.
    """
    def __init__(self, erst_id, cvrnummer, offentliggoerelsesTidspunkt,
                 reason):
        self.erst_id = erst_id
        self.cvrnummer = cvrnummer
        self.reason = reason
        self.offentliggoerelsesTidspunkt = offentliggoerelsesTidspunkt

    def __str__(self):
        msg = ("[erst_id = %s] "
               "[cvrnummer = %s] "
               "[offentliggoerelsesTidspunkt: %s] "
               "%s"
               ) % (
                   self.erst_id,
                   self.cvrnummer,
                   self.offentliggoerelsesTidspunkt,
                   self.reason
               )
        return msg


class InputRegnskab(object):
    """Responsible for providing financial_statement data based on the xbrl_file
    and its possible extension.
    """

    def __init__(self, cvrnummer, offentliggoerelsesTidspunkt,
                 xbrl_file_url, xbrl_extension_url, erst_id,
                 indlaesningsTidspunkt):
        self.cvrnummer = cvrnummer
        self.erst_id = erst_id
        self.offentliggoerelsesTidspunkt = offentliggoerelsesTidspunkt
        self.indlaesningsTidspunkt = indlaesningsTidspunkt
        self.xbrl_file_url = xbrl_file_url
        self.xbrl_file_contents = self._download_file(xbrl_file_url)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def _download_file(self, xbrl_file_url):
        response = requests.get(xbrl_file_url)
        if response.status_code != 200:
            error_msg = ('Status code when attempting to download file '
                         'was %s' % response.status_code)
            raise InputRegnskabError(self.erst_id, self.cvrnummer,
                                     self.offentliggoerelsesTidspunkt,
                                     error_msg)
        try:
            self.xbrl_charset = response.encoding
            return response.text.encode(response.encoding).decode('utf-8')
        except OSError as exc:
            print("OSERROR")
            error_msg = 'Error: could not decode xbrl file: %s\n' % (
                xbrl_file_url
            )
            raise InputRegnskabError(self.erst_id, self.cvrnummer,
                                     self.offentliggoerelsesTidspunkt,
                                     error_msg)
        return None


def query_by_erst_id(erst_id):
    url = 'https://distribution.virk.dk:8443'
    client = Elasticsearch(url, timeout=300, max_retries=10, retry_on_timeout=True, headers={'Content-Type': 'application/xml'})
    index = 'offentliggoerelser'
    search = Search(using=client, index=index).query(
        'match', _id=erst_id
    )
    response = search.execute()
    hits = response.hits.hits
    return hits, search


# Algorithm:
# Input: URL of xbrl file, URL of zip file and other meta info.
# write to temporary files and folders.
# prepare for arelle pass
# write to temporary csv
# fix temporary csv
# insert csv into database.

def process(cvrnummer, offentliggoerelsesTidspunkt, xbrl_file, xbrl_extension,
            erst_id, indlaesningsTidspunkt, unit_handler):
    if erst_id_present(erst_id):
        # print("ERST ID ERROR")
        return
    try:
        with InputRegnskab(cvrnummer, offentliggoerelsesTidspunkt,
                           xbrl_file, xbrl_extension, erst_id,
                           indlaesningsTidspunkt) as regnskab:
            drive_regnskab(regnskab)
            # print("finihsed input")
    except InputRegnskabError as e:
        print("YEEEEEEEEEE")
        with open('erst_data_errors.txt', 'a') as f:
            print(e, file=f, flush=True)
    except Exception as e:
        print("ERROR HERE")
        import traceback
        etype, exc, tb = sys.exc_info()
        msg = '[erst_id = %s] Caught Exception.\n' % erst_id
        msg += ''.join(traceback.format_tb(tb))
        print(msg, file=sys.stderr, flush=True)
    return


# def process(cvrnummer, offentliggoerelsesTidspunkt, xbrl_file, xbrl_extension,
#             erst_id, indlaesningsTidspunkt, unit_handler):
#     print(f"DEBUG: Starting process for erst_id: {erst_id}")
    
#     print(f"DEBUG: Checking if erst_id {erst_id} is present...")
#     if erst_id_present(erst_id):
#         print(f"DEBUG: ERST ID {erst_id} already present - returning early")
#         print("ERST ID ERROR")
#         return
    
#     print(f"DEBUG: erst_id {erst_id} not present, proceeding...")
    
#     try:
#         print(f"DEBUG: Creating InputRegnskab for erst_id: {erst_id}")
#         print(f"DEBUG: Parameters - cvr: {cvrnummer}, date: {offentliggoerelsesTidspunkt}")
#         print(f"DEBUG: xbrl_file: {xbrl_file}")
#         print(f"DEBUG: xbrl_extension: {xbrl_extension}")
        
#         with InputRegnskab(cvrnummer, offentliggoerelsesTidspunkt,
#                            xbrl_file, xbrl_extension, erst_id,
#                            indlaesningsTidspunkt) as regnskab:
#             print(f"DEBUG: InputRegnskab created successfully for {erst_id}")
#             print(f"DEBUG: About to call drive_regnskab for {erst_id}")
#             drive_regnskab(regnskab)
#             print(f"DEBUG: drive_regnskab completed for {erst_id}")
#             print("finihsed input")
#     except InputRegnskabError as e:
#         print(f"DEBUG: InputRegnskabError for {erst_id}: {e}")
#         print("YEEEEEEEEEE")
#         with open('erst_data_errors.txt', 'a') as f:
#             print(e, file=f, flush=True)
#     except Exception as e:
#         print(f"DEBUG: General Exception for {erst_id}: {e}")
#         print("ERROR HERE")
#         import traceback
#         etype, exc, tb = sys.exc_info()
#         msg = '[erst_id = %s] Caught Exception.\n' % erst_id
#         msg += ''.join(traceback.format_tb(tb))
#         print(msg, file=sys.stderr, flush=True)
#     return

def debug_by_erst_id(erst_id):
    # datetime_format = '%Y-%m-%dT%H:%M:%S.%f'
    hits, reponse = query_by_erst_id(erst_id)
    hit = hits[0]
    cvrnummer = hit['_source']['cvrNummer']
    offentliggoerelsesTidspunkt = hit['_source']['offentliggoerelsesTidspunkt']
    offentliggoerelsesTidspunkt = offentliggoerelsesTidspunkt[:19]
    offentliggoerelsesTidspunkt = parse_date(offentliggoerelsesTidspunkt)

    indlaesningsTidspunkt = hit['_source']['indlaesningsTidspunkt'][:19]
    indlaesningsTidspunkt = parse_date(indlaesningsTidspunkt)

    assert(erst_id == hit['_id'])

    dokumenter = hit['_source']['dokumenter']
    xbrl_file_url = None
    xbrl_extension_url = None
    import json
    print(json.dumps(hit, indent=2))
    print()
    for dokument in dokumenter:
        if (dokument['dokumentMimeType'].lower() == 'application/xml' and
                dokument['dokumentType'].lower() == 'aarsrapport'):
            xbrl_file_url = dokument['dokumentUrl']
        elif dokument['dokumentMimeType'].lower() == 'application/zip':
            xbrl_extension_url = dokument['dokumentUrl']

    if xbrl_file_url is not None:
        regnskab = InputRegnskab(cvrnummer, offentliggoerelsesTidspunkt,
                                 xbrl_file_url, xbrl_extension_url, erst_id,
                                 indlaesningsTidspunkt)
        drive_regnskab(regnskab)
    return


def erst_id_present(erst_id):
    # print(f"DEBUG: erst_id_present() starting for {erst_id}")
    
    try:
        # print(f"DEBUG: Creating session...")
        session = Session()
        # print(f"DEBUG: Session created: {session}")
        
        # print(f"DEBUG: About to execute query for {erst_id}")
        erst_id_found = session.query(FinancialStatement.erst_id).filter(
            FinancialStatement.erst_id == erst_id
        ).first()
        # print(f"DEBUG: Query executed, result: {erst_id_found}")
        
        result = erst_id_found is not None
        # print(f"DEBUG: Returning {result} for {erst_id}")
        return result
        
    except Exception as e:
        print(f"DEBUG: Exception in erst_id_present: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return False  # or re-raise depending on your needs
    finally:
        try:
            # print(f"DEBUG: Closing session...")
            session.close()
            # print(f"DEBUG: Session closed")
        except Exception as e:
            print(f"DEBUG: Error closing session: {e}")

def error_elastic_cvr_none(erst_id, offentliggoerelsesTidspunkt):
    msg = ("[erst_id = %s] [offentliggoerelsesTidspunkt: %s] "
           "Error: CVR-nummer returned by elasticsearch was None") % (
               erst_id, offentliggoerelsesTidspunkt
           )
    print(msg, file=sys.stderr, flush=True)
    return


def consumer_insert(queue, unit_handler=None, queue_lock=None):
    process_id = os.getpid()
    print(f"DEBUG: Consumer process {process_id} starting")
    
    # Initialize database connection for this process
    try:
        # print(f"DEBUG: Process {process_id} - calling setup_database_connection()")
        setup_database_connection()
        # print(f"DEBUG: Process {process_id} - database connection established")
        # Test creating a session
        test_session = Session()
        test_session.close()
        # print(f"DEBUG: Process {process_id} - Session test successful")
        
    except Exception as e:
        print(f"ERROR: Process {process_id} failed to setup database: {e}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        return
    
    if unit_handler is None:
        unit_handler = UnitHandler()
    
    processed_count = 0
    while True:
        msg = None
        try:
            queue_lock.acquire()
            if queue.size() == 0:
                queue_lock.release()
                time.sleep(2)
                continue
            
            msg = queue.get()
            popped, pushed = queue.get_statistics()
            print(ERASE + 'Inserting into db: %s/%s' % (popped, pushed),
                  end='', flush=True)
        finally:
            try:
                queue_lock.release()
            except:
                pass

        if isinstance(msg, str) and msg == 'DONE':
            break
            
        cvrnummer, offentliggoerelsesTidspunkt, xbrl_file_url = msg[:3]
        xbrl_extension_url, erst_id, indlaesningsTidspunkt = msg[3:]
        offentliggoerelsesTidspunkt = parse_date(offentliggoerelsesTidspunkt)
        indlaesningsTidspunkt = parse_date(indlaesningsTidspunkt)
        
        try:
            if cvrnummer is None:
                error_elastic_cvr_none(erst_id, offentliggoerelsesTidspunkt)
                continue
                
            # print(f"DEBUG: Process {process_id} processing record {processed_count}: {erst_id}")
            process(cvrnummer, offentliggoerelsesTidspunkt, xbrl_file_url,
                    xbrl_extension_url, erst_id, indlaesningsTidspunkt,
                    unit_handler)
            processed_count += 1
            # print(f"DEBUG: Process {process_id} completed record {processed_count}")
            
        except Exception as e:
            print(f"ERROR: Process {process_id} failed on record {erst_id}: {e}")
            import traceback
            print(f"ERROR: Traceback: {traceback.format_exc()}")
    
    print(f"DEBUG: Process {process_id} finished, processed {processed_count} records")
    return


def make_input_regnskab_from_search(s):
    r = s.execute()
    result = r[0]
    cvr = result.cvrNummer
    offentliggoerelsesTidspunkt = result.offentliggoerelsesTidspunkt
    try:
        tmp = [d for d in result.dokumenter
               if d['dokumentType'] == 'AARSRAPPORT' and
               d['dokumentMimeType'] == 'application/xml']
        xbrl_file_url = tmp[0]['dokumentUrl']
    except Exception:
        raise
    xbrl_extension_url = ''
    erst_id = result.meta['id']
    indlaesningsTidspunkt = result.indlaesningsTidspunkt
    return InputRegnskab(cvr, offentliggoerelsesTidspunkt, xbrl_file_url,
                         xbrl_extension_url, erst_id, indlaesningsTidspunkt)


def producer_scan(search_result, queue, queue_lock=None):
    for document in search_result.scan():
        erst_id = document.meta.id
        cvrnummer = document['cvrNummer']
        # cvrnummer is possibly None, e.g. Greenland companies

        # date format: Y-m-dTH:M:s[Z+x]
        offentliggoerelsesTidspunkt = document['offentliggoerelsesTidspunkt']
        offentliggoerelsesTidspunkt = offentliggoerelsesTidspunkt[:19]
        indlaesningsTidspunkt = document['indlaesningsTidspunkt'][:19]

        dokumenter = document['dokumenter']
        xbrl_file_url = None
        xbrl_extension_url = None
        for dokument in dokumenter:
            mime_type = dokument['dokumentMimeType'].lower()
            xml_type = 'application/xml'
            dokument_type = dokument['dokumentType'].lower()
            if (mime_type == xml_type and dokument_type == 'aarsrapport'):
                xbrl_file_url = dokument['dokumentUrl']
            elif mime_type == 'application/zip':
                # TODO: dokument['dokumenType'].lower() == ?
                xbrl_extension_url = dokument['dokumentUrl']
        if xbrl_file_url is not None:

            msg = (cvrnummer, offentliggoerelsesTidspunkt, xbrl_file_url,
                   xbrl_extension_url, erst_id, indlaesningsTidspunkt)
            queue_lock.acquire()
            queue.put(msg)
            popped, pushed = queue.get_statistics()
            print(ERASE + 'Inserting into db: %s/%s' % (popped, pushed),
                 end='', flush=True)
            queue_lock.release()
    return


def get_virk_search(from_date):
    client = elasticsearch.Elasticsearch('http://distribution.virk.dk:80',
                                          timeout=300, max_retries=10, retry_on_timeout=True)
    s = Search(using=client, index='offentliggoerelser')
    s = s.filter('range', offentliggoerelsesTidspunkt={'gte': from_date})
    s = s.sort('offentliggoerelsesTidspunkt')

    elastic_search_scan_size = 1000
    elastic_search_scroll_time = u'5m'

    params = {'scroll': elastic_search_scroll_time, 'size': elastic_search_scan_size}

    s = s.params(**params)
    s = s.query('match_all')
    return s


def fetch_to_db(process_count=1, from_date=datetime(2011, 1, 1)):
    setup_tables()

    unit_handler = UnitHandler()
    s = get_virk_search(from_date)
    try:
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        m = IOQueueManager()
        m.start()
        print(tmp_file.name)
        queue = m.IOQueue(tmp_file.name)
        queue_lock = Lock()
        consumer_partial = functools.partial(consumer_insert,
                                             queue_lock=queue_lock,
                                             unit_handler=unit_handler)

        processes = [Process(target=consumer_partial,
                             args=(queue,),
                             daemon=True) for _ in range(process_count)]
        
        for p in processes:
            p.start()
        #print("DISPOSING ENGINE")
        engine.dispose()  # for multiprocessing.
        producer_scan(s, queue, queue_lock=queue_lock)

        queue_lock.acquire()
        for end in range(process_count):
            queue.put('DONE')
        queue_lock.release()

        for p in processes:
            p.join()

    finally:
        os.remove(tmp_file.name)
        pass
    return
