from config import settings
import psycopg2
import logging
import string
import random
import re

log = logging.getLogger('dh')
logging.basicConfig()
log.setLevel(logging.INFO)



CREATE_VERSION_SQL = "insert into versions (name, repo, user_id) values (%s,%s,%s) RETURNING v_id"
CREATE_VERSION_PARENT = "insert into version_parent (child_id, parent_id) values (%s,%s)"
CREATE_VERSIONED_TABLE = "insert into versioned_table (real_name, display_name, repo) values (%s,%s,%s)"
CREATE_VERSIONS_TABLE = "insert into versions_table (real_name, v_id) values (%s,%s)"
FREEZE_TABLES = "update versioned_table set copy_on_write = true where real_name in (select real_name from versions_table where v_id = %s)"
FREEZE_TABLE =  "update versioned_table set copy_on_write = true where real_name = %s"
COPY_VERSIONS = "insert into versions_table (real_name, v_id) select real_name, %s from versions_table where v_id = %s" 
GET_TABLE = "select real_name, display_name, repo, copy_on_write from versioned_table where real_name = %s"
GET_TABLE_DISP_COUNT = "select count(*) from versioned_table where display_name = %s and repo=%s"
MOD_TABLE_DH_ATTRS = "alter table %s add column _dh_delbit boolean default false;"
CLONE_TABLE = "CREATE TABLE %s as select * from %s with no data"
CREATE_TABLE_PARENT= "insert into versioned_table_parent (child_table, parent_table) values (%s,%s)"
GET_V_ID = "select v_id from versions where repo = %s and name = %s"

class SQLVersioning:
  
  def __init__(self):
    self.connection = psycopg2.connect(
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT'],
        database=settings.DATABASES['default']['NAME'])

  #Create a new version. may not have a parent
  def create_version(self, user, repo, v_name, parent_v_id=None):
    cur = self.connection.cursor()
    id = None
    try:
      cur.execute(CREATE_VERSION_SQL,(v_name,repo,user))
      r = True
      id = cur.fetchone()[0]
      log.info("Id %s" % id)
    except Exception, e:
      r = False
      log.error(e)
    if r and parent_v_id:
      try:
        if isinstance(parent_v_id, int):
          cur.execute(CREATE_VERSION_PARENT,(id, parent_v_id))  
          cur.execute(COPY_VERSIONS, (id,parent_v_id))
        else:
          raise Exception("not supported parent type %s " % parent_v_id)
      except Exception, e:
        r = False
        log.error(e)      
    if r:
      self.connection.commit()
    cur.close()
    return id
  
  #Find the version id for a named version
  def get_v_id(self,repo,v_name):
    cur = self.connection.cursor()
    v = None
    try:
      cur.execute(GET_V_ID,(repo, v_name))
      v = cur.fetchone()[0]
      self.connection.commit()
    except Exception, e:
      log.error(e)      
    cur.close()
    return v
  
  
  #Find the active table to insert into given a version and table name
  def find_active_table(self, version, display_table_name):
    raise Exception("TODO find_active_table")
  
  def get_list_tables(self, v_id):
    log.error("TODO get_list_tables")
    return []
                      
  def gen_string(self,base='', n=6):
    return "%s_%s" % (base,''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n)))
  
  def build_table_query(self, table_tail):
    raise Exception("TODO")
  
  def get_rs(self,sql):
    raise Exception("TODO")
    
  #Freeze all the tables associated with a version
  def freeze_tables(self, v_id):
    cur = self.connection.cursor()
    try:
      cur.execute(FREEZE_TABLES,(v_id,))
      self.connection.commit()
    except Exception, e:
      log.error(e)      
    cur.close()

  def freeze_table(self,table_real_name):
    cur = self.connection.cursor()
    try:
      cur.execute(FREEZE_TABLE,(table_real_name,))
      self.connection.commit()
    except Exception, e:
      log.error(e)      
    cur.close()

  #placeholder for proper SQL parsing
  def replace_table_name(self, old_table, new_table, sql):
    return re.sub(old_table, new_table, sql)

  #Any validation of DH create statements
  def validate_extend_create_sql(self, sql):
    log.error("TODO")
    return sql

  #Create a new table associated with a version
  def create_table(self, user, repo, table_display_name, create_sql, v_id):
    log.info("Create table")
    rn = None
    cur = self.connection.cursor()
    try:
      #Ensure that no other display name exists in the repo
      cur.execute(GET_TABLE_DISP_COUNT,(table_display_name,repo))
      cnt = cur.fetchone()[0]
      if cnt != 0:
        raise Exception("Table with display_name %s already exists in repo %s" % (table_display_name,repo))
      rn = self.gen_string(table_display_name)
      #Create the metadata for versioned table
      cur.execute(CREATE_VERSIONED_TABLE,(rn, table_display_name, repo))   
      cur.execute(CREATE_VERSIONS_TABLE, (rn,v_id))
      #Update create statement
      mod_sql = self.replace_table_name(table_display_name, rn, create_sql)
      mod_sql = self.validate_extend_create_sql(mod_sql)
      #create the db
      cur.execute(mod_sql)
      # add Delete bit
      cur.execute(MOD_TABLE_DH_ATTRS%rn)
      self.connection.commit()
    except Exception, e:
      log.error(e)
      rn = None
    cur.close()
    return rn    

  #clone a table 
  def clone_table(self,table_real_name, new_name=None):
    cur = self.connection.cursor()
    try:
      #find the table information for source table
      cur.execute(GET_TABLE,(table_real_name,))
      r = cur.fetchone()
      rn = self.gen_string(r[1])
      #create the meta data
      cur.execute(CREATE_VERSIONED_TABLE,(rn, r[1], r[2]))
      cur.execute(CREATE_TABLE_PARENT, (rn,table_real_name))
      #create a copy of source table
      sql = CLONE_TABLE%(rn, table_real_name)
      cur.execute(sql)
      self.connection.commit()
    except Exception, e:
      log.error(e)
      rn = None
    cur.close()
    return rn
    
  def get_query_trace(self, v_id1, v_id2):
    raise Exception("TODO")
  
  def update_user_head(self, user, repo, v_id, v_name):
    raise Exception("TODO")
  

  
  def commit(self, query_list, v_id):
    #update query log
    #insert into active table of v
    raise Exception("TODO")
