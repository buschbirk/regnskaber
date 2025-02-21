import argparse
import datetime

from . import (interactive_ensure_config_exists, setup_database_connection,
               parse_date, interactive_configure_connection)

from . import fetch
from . import make_feature_table as transform


class Commands:
    @staticmethod
    def fetch(from_date, processes, **general_options):
        interactive_ensure_config_exists()
        # setup engine and Session.
        setup_database_connection()
        fetch.fetch_to_db(processes, from_date)

    @staticmethod
    def transform(table_definition_file, replace_existing_table=False, **general_options):
        interactive_ensure_config_exists()
        # setup engine and Session.
        setup_database_connection()
        transform.main(table_definition_file, replace_existing_table=replace_existing_table)

    @staticmethod
    def reconfigure(**general_options):
        interactive_configure_connection()

parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(dest='command')
subparsers.required = True

parser_fetch = subparsers.add_parser('fetch', help='fetch from erst')
parser_fetch.add_argument('-f', '--from-date',
                          dest='from_date',
                          help='From date on the form: YYYY-mm-dd[THH:MM:SS].',
                          type=parse_date,
                          default=datetime.datetime(2011, 1, 1),
                          required=False)

parser_fetch.add_argument('-p', '--processes',
                          dest='processes',
                          help=('The number of parallel jobs to start.'),
                          type=int,
                          default=1)

parser_transform = subparsers.add_parser('transform',
                                         help=('build useful tables from data '
                                               'fetched from erst.'))
parser_transform.add_argument('table_definition_file', type=str,
                              help=('A file that specifies the table to be '
                                    'created'))
parser_transform.add_argument('-r', '--replace-existing-table', dest='replace_existing_table', 
                              help=('If true, table is dropped if it already exists. '
                                    'If false, keeps table and continues parsing from next available financial statement'),
                              default=False,
                              action='store_true')


parser_reconfigure = subparsers.add_parser('reconfigure',
                                           help='Reconfigure database info.')


if __name__ == "__main__":
    args = vars(parser.parse_args())
    getattr(Commands, args.pop('command'))(**args)
