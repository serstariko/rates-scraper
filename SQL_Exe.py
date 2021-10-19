# -*- coding: utf-8 -*-
"""
Created on Tue May  7 10:38:53 2019

@author: MAFedorov
"""
import pandas as pd
import cx_Oracle
import datetime as dt
import xlwings as xw
import os

from sqlalchemy import types, create_engine
     
#Настройка среды: Oracle client and lang
os.environ['PATH'] = 'C:\\instantclient_12_2' + ';' + os.environ['PATH'] 
os.environ["NLS_LANG"] = "RUSSIAN_RUSSIA.AL32UTF8"

def SQLFromFile(filename):

    # Open and read the file as a single buffer
    fd = open(filename, 'r')
    sql = fd.read()
    fd.close()
    
    sql = sql.replace('\n',' ')
    
    return sql
                

def query2excel(outlist, outrange, sqlfile, login, pwd, tnsname, paramdict):
    
    wb = xw.Book.caller()
    sht = wb.sheets[outlist]
    
    query=SQLFromFile(sqlfile)
    df = selquery(query, paramdict, login, pwd, tnsname)
    
    sht.range(outrange).options(index=False, header=False).value = df


    
#######--пока только сигнатура
def query2csv(outlist, outrange, sqlfile, login, pwd, tnsname, paramdict):
  pass
#######-----------------------



def selquery(query, paramdict, login, pwd, tnsname):
    
    conn = cx_Oracle.connect(login, pwd, tnsname, encoding = "UTF-8")

    cur = conn.cursor()
    cur.prepare(query)
     
    print(query)
    if (paramdict == False):
        print('Запрос без параметров')
        tt=cur.execute(None)
    else:
        print('Запрос с параметрами')
        tt=cur.execute(None, paramdict)      
    ##print('commit')
    conn.commit()
    ##ss = cur.statement
    
    if (query.lower().startswith('select') | query.lower().startswith('with')):   
        col_names = [i[0] for i in cur.description]
        #print('Cursor.statement: ', cur.statement)  
        #print('Cursor.fetchvars: ', cur.fetchvars)
        #print('Cursor.description:', cur.description)
        df = pd.DataFrame(cur.fetchall(), columns=col_names)   
        cur.close()
        conn.close()      
        return df
    
    else:
        return 'Done ' + str(tt)
    

def insquery(tab, df, login, pwd, tnsname):
    print('_iq_step0_')
    #engine = create_engine('oracle+cx_oracle://%s:%s@%s' % (login, pwd, tnsname),  encoding = "utf-8",  max_identifier_length=128)
    engine = create_engine('oracle+cx_oracle://%s:%s@%s' % (login, pwd, tnsname),  encoding = "utf-8")
    print('_iq_step1_')
    dtyp = {c:types.VARCHAR(df[c].str.len().max()) for c in df.columns[df.dtypes == 'object'].tolist()}
    print('_iq_step2_')
    df.to_sql(tab, engine, index=False, if_exists='append', dtype=dtyp)
    print('_iq_step3_')

#Переименуем таблтицу
def RenameTbl(tbl1, tbl2, login, pwd, tnsname):

    q='ALTER TABLE ' + tbl1 + ' RENAME TO ' + tbl2
    st= selquery(q, False, login, pwd, tnsname)
    print(st + 'Таблица переименована')


#Изменение размера таблицы
def ResizeTbl(tbl, login, pwd, tnsname):
    q='create table ' + tbl + '_1 as select * from ' + tbl
    st= selquery(q, False, login, pwd, tnsname)
    print(st)
    
    q='drop table ' + tbl
    st= selquery(q, False, login, pwd, tnsname)
    print(st)
    
    q='ALTER TABLE ' + tbl + '_1 RENAME TO ' + tbl
    st= selquery(q, False, login, pwd, tnsname)
    print(st)

#Удаляем данные из таблицы
def DeleteTbl_DtoD(tbl, dtsym, dt1, dt2, login, pwd, tnsname):
     
    q = f""" delete from {tbl} where {dtsym} 
               between to_date('{dt1}', 'dd.mm.yyyy') 
               and to_date('{dt2}', 'dd.mm.yyyy') 
          """     
    st = selquery(q, False, login, pwd, tnsname)
     
    print(st)




def Run_SQL_Test():

   # os.environ['PATH'].split(';')
   # os.environ['PATH'] = 'C:\\instantclient_12_2' + ';' + os.environ['PATH'] 


    wb = xw.Book.caller()
    
     #   wb =xw.apps[0].books['ГЭП_7_30_CFT.xlsm']
         
    date1 = xw.Range('upl_dt_cf_cfl').options(dates=dt.date).value
    date1 = xw.Range('upl_dt_cf_cfl').options(dates=dt.date).value
    outlist= xw.Range('outlist_cf_cfl').value
    outrange= xw.Range('outputrange_cf_cfl').value
        
    sqlfile=xw.Range('sqlfile_cf_cfl').value
    
    #conn = cx_Oracle.connect('DOKR_INVEST', 'DOKR_INVEST', 'DWH', encoding="utf-8")
    #sqlfile='C:\cft_report\cf_cfl_ondate.sql'
    
    query=SQLFromFile(sqlfile)
    
    sht = wb.sheets[outlist]
    
    login= xw.Range('user_ehd').options(dates=dt.date).value
    pwd= xw.Range('pwd_ehd').options(dates=dt.date).value
    tnsname= xw.Range('tns_ehd').options(dates=dt.date).value
        
    conn = cx_Oracle.connect(login, pwd, tnsname, encoding = "UTF-8")
    cur = conn.cursor()

    cur.prepare(query)
    
    cur.execute(None, {'date1':date1})
    
    df = pd.DataFrame(cur.fetchall())   
    
    sht.range(outrange).options(index=False, header=False).value = df
    conn.close()