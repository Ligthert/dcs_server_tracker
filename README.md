# dcs_server_tracker
Frontend for historical data of DCS World servers.

## Requirements
* MySQL (any recent version)
* Redis (any recent version)
* Python 3 + some modules
* GeoIP2

## Installation
Quick 'n dirty install!

I will be using Debian, but any other Unix flavour is fine

### 1. Install docker and the services we need
```
$ sudo apt-get install docker.io
$ sudo docker run --name redis -p 127.0.0.1:6379:6379 -d redis redis-server --appendonly yes
$ sudo docker run --name mysql -p 127.0.0.1:3306:3306 -e MYSQL_ROOT_PASSWORD=sqlpassword -d mysql:5.7
```

### 2. Install a recent version of GeoIP2 and unpack it
```
$ wget https://geolite.maxmind.com/download/geoip/database/GeoLite2-Country.tar.gz
$ tar -zxpvf GeoLite2-Country.tar.gz
```

### 3. Install Python 3 and our dependencies
```
$ apt-get install python3-pip
$ pip3 install -r requirements.txt
$ apt-get install default-mysql-client
```

### 4. Download the installation the software and configure MySQL
Make a clone of the repo
```
$ git clone https://github.com/GlowieXYZ/dcs_server_tracker.git
```

Configure MySQL
```
$ mysql -h 127.0.0.1 -u root -psqlpassword
> create database dcs_server_tracker;
> grant all on dcs_server_tracker.* to dcst identified by 'dcstpassword';
```

Prepare the database
```
cat dcs_server_tracker.sql | mysql -h 127.0.0.1 -u root -psqlpassword dcs_server_tracker
```


## Configuration
The applications is configured using environmental variables. These are the following.

### DCS Account
Login credentials to login at www.digitalcombatsimulator.com and get the list of servers
* `DCS_SERVER_TRACKER_ED_USER`
* `DCS_SERVER_TRACKER_ED_PASS`

### Redis
Redis server, port and db #
* `DCS_SERVER_TRACKER_REDIS_IP`
* `DCS_SERVER_TRACKER_REDIS_PORT`
* `DCS_SERVER_TRACKER_REDIS_DB`

### MySQL
Fill in your MySQL info here
* `DCS_SERVER_TRACKER_MYSQL_SERVER`
* `DCS_SERVER_TRACKER_MYSQL_PORT`
* `DCS_SERVER_TRACKER_MYSQL_DATABASE`
* `DCS_SERVER_TRACKER_MYSQL_USERNAME`
* `DCS_SERVER_TRACKER_MYSQL_PASSWORD`

### GeoIP2
Point this to where your GeoLite2-Country.mmdb is stored
* `DCS_SERVER_TRACKER_GEOIP2_FILE`

### Python 3
This will make your life easier:
* `$ export PYTHONIOENCODING=utf-8`

## Hints and Tips
If you are lazy and need to test stuff, create a shell script that sets all these environmental variables.
