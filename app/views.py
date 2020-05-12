from flask import render_template, url_for, redirect, request, send_from_directory
# from flask_cache import Cache
from datetime import datetime
import os
import json
import time
from app import app
from pprint import pprint
from operator import itemgetter
import redis
import pickle
import pymysql
import hashlib

# import dstw
# Global var, ugly. I know. :-(
rconn = redis.Redis(host=os.environ["DCS_SERVER_TRACKER_REDIS_IP"],port=os.environ["DCS_SERVER_TRACKER_REDIS_PORT"],db=os.environ["DCS_SERVER_TRACKER_REDIS_DB"])

def executeQuery(query,params=[],type="all",expiry=240):
  queryHash = "query_"+hashlib.md5(str(query+str(params)).encode()).hexdigest()
  if rconn.exists(queryHash) == 1:
    return pickle.loads(rconn.get(queryHash))
  db = pymysql.connect(host=os.environ["DCS_SERVER_TRACKER_MYSQL_SERVER"],
    port=int(os.environ["DCS_SERVER_TRACKER_MYSQL_PORT"]),
    user=os.environ["DCS_SERVER_TRACKER_MYSQL_USERNAME"],
    password=os.environ["DCS_SERVER_TRACKER_MYSQL_PASSWORD"],
    db=os.environ["DCS_SERVER_TRACKER_MYSQL_DATABASE"],
    cursorclass=pymysql.cursors.DictCursor,
    use_unicode=True,
    charset="utf8")
  db.autocommit(True)
  cursor = db.cursor()
  cursor.execute(query,params)
  cursor.close()
  db.close()
  if type=="all":
    rconn.set(queryHash,pickle.dumps(cursor.fetchall()))
    rconn.expire(queryHash,expiry)
    return pickle.loads(rconn.get(queryHash))
  elif type=="one":
    rconn.set(queryHash,pickle.dumps(cursor.fetchone()))
    rconn.expire(queryHash,expiry)
    return pickle.loads(rconn.get(queryHash))


sql_servers_online = "SELECT * FROM servers WHERE status='up'"
sql_servers_offline = "SELECT * FROM servers WHERE status='down'"
sql_servers_both = "SELECT * FROM servers"

sql_server_select = "SELECT * FROM servers WHERE INSTANCE_ID=%s"
sql_server_history = "SELECT * FROM scenarios WHERE instance_id=%s ORDER BY start DESC"
sql_server_players = "SELECT * FROM players WHERE INSTANCE_ID=%s ORDER BY TIMESTAMP ASC"
sql_server_samehost = "SELECT * FROM servers WHERE IP_ADDRESS=%s AND PORT!=%s ORDER BY PORT"

#sql_server_update_country_iso = "UPDATE servers SET country_iso=%s WHERE INSTANCE_ID=%s"
#sql_server_update_country_name = "UPDATE servers SET country_name=%s WHERE INSTANCE_ID=%s"

sql_stats_online = "SELECT * FROM servers WHERE status='up'"
sql_stats_all = "SELECT * FROM servers"

# The default/servers page
@app.route("/")
@app.route("/servers/")
def page_servers():
  edJSON = fetchJSON()

  search_prep={}
  search_active = {}

  search_prep['servers'] = request.args.get('servers', default = 'online', type = str)
  search_prep['column'] = request.args.get('column', default = 'players', type = str)
  search_prep['order'] = request.args.get('order', default = 'desc', type = str)

  # Depending on search queries sort stuff
  if search_prep['column'] == "players":
    search_field = "PLAYERS"
  elif search_prep['column'] == "servers":
    search_field = "NAME"
  elif search_prep['column'] == "scenario":
    search_field = "MISSION_NAME"
  elif search_prep['column'] == "countries":
    search_field = "country_iso"
  else:
    search_field = "PLAYERS"

  if search_prep['order'] == "desc":
    search_order = True
    search_order_sql = "DESC"
  elif search_prep['order'] == "asc":
    search_order = False
    search_order_sql = "ASC"
  else:
    search_order_sql = "DESC"

  if search_prep['servers'] == "online":
    servers = executeQuery(sql_servers_online)
    search_active['servers_online'] = True
  elif search_prep['servers'] == "offline":
    servers = executeQuery(sql_servers_offline)
    search_active['servers_offline'] = True
  elif search_prep['servers'] == "both":
    servers = executeQuery(sql_servers_both)
    search_active['servers_both'] = True
  else:
    servers = edJSON['SERVERS']
    search_active['servers_online'] = True

  # Prepare the list of servers for publication
  for server in servers:
    server['name'] = str(server['NAME'])[:120]
    server['players'] = int(server['PLAYERS'])
    server['instance_id'] = str(server['IP_ADDRESS'])+":"+str(server['PORT'])
    if server['DESCRIPTION'] == "No":
      server['DESCRIPTION'] = ""
    else:
      server['DESCRIPTION'] = server['DESCRIPTION'].replace('<br />','')
    if server['PASSWORD']=="No":
      del server['PASSWORD']


  # Sort the list
  servers = sortListofDicts(servers,search_field,search_order)

  # Print everything to screen
  content = render_template("servers.html", server_count=len(edJSON['SERVERS']), player_count=edJSON['PLAYERS_COUNT'], servers=servers, search_prep=search_prep, search_active=search_active)
  active = {"servers":True}
  edJSON = fetchJSON()
  return render_template("template.html", title="DCS Server Tracker", content=content, active=active, last_update=timestamp_pretty(edJSON['timestamp']))


# Show data of a specific server
@app.route("/servers/<string:instance_id>")
def page_server(instance_id):
  server = executeQuery(sql_server_select, [instance_id],"one")

  server['DESCRIPTION'] = str(server['DESCRIPTION']).replace('%lt;','<')
  server['DESCRIPTION'] = str(server['DESCRIPTION']).replace('%gt;','>')
  server['DESCRIPTION'] = str(server['DESCRIPTION']).replace('&nbsp;','&')
  server['MISSION_TIME_FORMATTED'] = str(server['MISSION_TIME_FORMATTED']).replace('&nbsp;','&')
  if server['PASSWORD']=="No":
    del server['PASSWORD']
  if server['status']=="down":
    del server['status']

  server['samehost'] = executeQuery(sql_server_samehost,[server['IP_ADDRESS'],server['PORT']])

  results = executeQuery(sql_server_players, [instance_id])
  values = []
  for result in results:
    value = {}
    value['key'] = timestamp_timeonly(result['timestamp'])
    value['val'] = result['players']
    values.append(value)

  history = executeQuery(sql_server_history, [instance_id])
  for event in history:
    event['start'] = timestamp_pretty(event['start'])
    event['end'] = timestamp_timeonly(event['end'])

  content = render_template("server.html", server=server, values=values, history=history)
  active = {"servers":True}
  edJSON = fetchJSON()
  return render_template("template.html", title=server['NAME']+" - DCS Server Tracker", content=content, active=active, last_update=timestamp_pretty(edJSON['timestamp']))


# The /stats-page with whatever stats
@app.route("/stats/")
def page_stats():

  metadata = pickle.loads(rconn.get("dcst_stats_metadata"))
  countrydata = pickle.loads(rconn.get("dcst_stats_countrydata"))
  allPlayers = pickle.loads(rconn.get("dcst_stats_allPlayers"))
  countrydataall = pickle.loads(rconn.get("dcst_stats_countrydataall"))

  content = render_template("stats.html", metadata=metadata, countrydata=countrydata, allPlayers=allPlayers, countrydataall=countrydataall)
  active = {"stats":True}
  edJSON = fetchJSON()
  return render_template("template.html", title="Stats - DCS Server Tracker", content=content, active=active, last_update=timestamp_pretty(edJSON['timestamp']))


# The /about-page is just a formality at this point really
@app.route("/about/")
def page_about():
  content = render_template("about.html")
  active = {"about":True}
  edJSON = fetchJSON()
  return render_template("template.html", title="About - DCS Server Tracker", content=content, active=active, last_update=timestamp_pretty(edJSON['timestamp']))


## Functions!

# Latest timestamp
def data_latest_meta():
  metadata = {}
  metadata['dcst_meta_players_count'] = str(rconn.lrange("dcst_meta_players_count",0,0)[0].decode()).split(",")[1]
  metadata['dcst_meta_servers_max_data'] = str(rconn.lrange("dcst_meta_servers_max_data",0,0)[0].decode()).split(",")[1]
  metadata['dcst_meta_servers_online'] = str(rconn.lrange("dcst_meta_servers_online",0,0)[0].decode()).split(",")[1]
  metadata['dcst_meta_servers_count'] = str(rconn.lrange("dcst_meta_servers_count",0,0)[0].decode()).split(",")[1]
  metadata['dcst_meta_servers_max_count'] = str(rconn.lrange("dcst_meta_servers_max_count",0,0)[0].decode()).split(",")[1]
  return metadata

# Print a timestamp pretty
def timestamp_pretty(timestamp):
  return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def timestamp_timeonly(timestamp):
  return datetime.utcfromtimestamp(timestamp).strftime('%H:%M:%S')

def fetchJSON():
  return pickle.loads( rconn.get("dcst_meta_servers_online") )

def sortListofDicts(myList,myColumn,reverse=False):
  return sorted(myList, key=itemgetter(myColumn), reverse=reverse)

def getCountryISO(instance_id):
  server = executeQuery(sql_server_select, [instance_id],"one")
  return server['country_iso']


def getCountryName(instance_id):
  server = executeQuery(sql_server_select, [instance_id],"one")
  return server['country_name']
