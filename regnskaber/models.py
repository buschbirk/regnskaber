from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (Column, Integer, String, DateTime, BigInteger, Text,
                        ForeignKey, Sequence, Boolean)
from sqlalchemy.orm import relationship
from sqlalchemy import Sequence, UniqueConstraint

Base = declarative_base()


class FinancialStatement(Base):

    __tablename__ = 'financial_statement'

    id = Column(Integer, Sequence('id_sequence'), primary_key=True)
    offentliggoerelsesTidspunkt = Column(DateTime)
    indlaesningsTidspunkt = Column(DateTime)
    cvrnummer = Column(BigInteger)
    erst_id = Column(String(length=100), index=True, unique=True)

    financial_statement_entries = relationship(
        'FinancialStatementEntry',
        back_populates='financial_statement',
        order_by='FinancialStatementEntry.id',
    )

    # __table_args__ = {'mysql_row_format': 'COMPRESSED'}


class FinancialStatementEntry(Base):

    __tablename__ = 'financial_statement_entry'

    id = Column(Integer, Sequence('id_sequence'), primary_key=True)
    financial_statement_id = Column(Integer,
                                    ForeignKey('financial_statement.id'))
    fieldName = Column(String(length=1000))
    fieldValue = Column(Text())
    decimals = Column(String(length=20))
    cvrnummer = Column(BigInteger)
    startDate = Column(DateTime)
    endDate = Column(DateTime)
    dimensions = Column(String(length=10000))
    unitIdXbrl = Column(String(length=100))
    koncern = Column(Boolean)

    financial_statement = relationship(
        'FinancialStatement',
        back_populates='financial_statement_entries',
    )

    # __table_args__ = {'mysql_row_format': 'COMPRESSED'}


class Header(Base):
    __tablename__ = 'header'
    id = Column(Integer, Sequence('id_seq'), primary_key=True)
    financial_statement_id = Column(Integer())
    consolidated = Column(Boolean())
    currency = Column(String(5))
    language = Column(String(5))
    balancedato = Column(DateTime)
    gsd_IdentificationNumberCvrOfReportingEntity = Column(BigInteger)
    gsd_InformationOnTypeOfSubmittedReport = Column(Text)
    gsd_ReportingPeriodStartDate = Column(DateTime)
    gsd_ReportingPeriodEndDate = Column(DateTime)
    fsa_ClassOfReportingEntity = Column(Text)
    cmn_TypeOfAuditorAssistance = Column(Text)

    __table_args__ = (
        UniqueConstraint('financial_statement_id', 'consolidated',
                         name='unique_financial_statement_id_consolidated'
                         ),
    )