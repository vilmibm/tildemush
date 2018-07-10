# running a little postgres database without sudo

Most system packages of PostgreSQL assume that you're a Database Administrator
who wants to use the computer as A Database Server running one blessed
PostgreSQL "cluster" of possibly many databases that other computers can access.

That's not me. When developing, I like to run "a little postgres" that:

- only touches files in a subdirectory of my project directory,
- doesn't start running when the system boots,
- doesn't talk to any other computers,
- requires no sudo access,
- doesn't leave logfiles around, and
- doesn't need me to manage a special database username or password, or specify
  that to all the database clients.

Since I'm only using this little cluster for the one local application,
I don't need to mess around with database names, user names, and passwords;
I just have my app use the postgres defaults.

Here's how to do that:

## Quickstart

For a walk-through with explanations, skip over this section to "Setup" instead.

```
export PATH=/usr/lib/postgresql/10/bin/:"$PATH"

export PGDATA="$PWD/pgdata"
export PGHOST="$PGDATA/sockets"
export PGDATABASE="postgres"
export PGUSER="$USER"

pg_ctl init

mkdir -p "$PGDATA/sockets"
echo "unix_socket_directories = 'sockets'" >> "$PGDATA/postgresql.conf"
echo "listen_addresses = ''" >> "$PGDATA/postgresql.conf"

pg_ctl start
createdb postgres_test # for tildemush unit tests
```

## Setup

### install postgres, somehow

* technically, this step will require sudo
    * unless you install it by hand within your home directory
    * or you have a cool system like GuixSD that lets normal users install
      packages
    * but that's a bit beyond the scope of these instructions
    
**debian**: `sudo apt-get install postgresql`

if you prefer, configure it not to start at boot time:

**debian**:

```
sudo systemctl disable postgresql
sudo systemctl stop postgresql
```

### locate `pg_ctl`

we'll be using the postgresql program `pg_ctl`.
figure out where it got installed.

* it might just be on your path: `which pg_ctl`
* on my debian box, it gets installed to `/usr/lib/postgresql/(version)/bin/`
* in instructions below, I'll say `/usr/lib/postgresql/10/bin/pg_ctl` but you
  can replace this with the path to yours.

### set some environment variables

```
export PGDATA="$PWD/pgdata"
export PGHOST="$PGDATA/sockets"
```

* This should be done from the root of your project directory, but you can
  adjust it as you like.
* I like to configure these to always be set by adding those lines to the end of
  the `venv/bin/activate` script. Otherwise you'll have to run them again next
  time you open a terminal to run the database and server.

### create the database "cluster"

one postgresql process can manage a bunch of databases for you. it calls that
collection of databases the "cluster".

we'll make one in a subdirectory of our projects directory.

`/usr/lib/postgresql/10/bin/pg_ctl init --auth-local trust --auth-host reject`

* this will look at $PGDATA to figure out that it should create files in the
  directory `pgdata`.
* you can leave off the --auth-local and --auth-host stuff. it will warn you,
  but it's safe.

### set up the sockets directory

usually postgres wants to put its sockets somewhere like `/var/run/postgresql/`.
but you need sudo for that!
so let's change it.

```
mkdir -p "$PGDATA/sockets"
echo "unix_socket_directories = 'sockets'" >> "$PGDATA/postgresql.conf"
```

usually postgres listens to its sockets, but also to a port on an ip address
like `localhost`.
which means you'd have to make sure that other instances of postgres aren't
trying to talk to the same port.
we don't need all that, and sockets are faster anyway!

```
echo "listen_addresses = ''" >> "$PGDATA/postgresql.conf"
```

### that's it

You'll need to do that stuff above once.
After that, here's how to use your database:

## Running

Remember, those environment variables need to be set.
If you didn't set that up to happen automatically, you'll have to do that again
now.
After that:

### start

`/usr/lib/postgresql/10/bin/pg_ctl start`

The database will run in the background and spew its logs into the current
terminal window.

### stop

`/usr/lib/postgresql/10/bin/pg_ctl stop`

### connecting clients

Most client software like `psql` can now connect to your database as long as it
has the same `$PGHOST` set in its environment.

Some software will pick its own connection settings that don't match
PostgreSQL's defaults.
For those, you may additionally need to set:

```
export PGDATABASE="postgres"
export PGUSER="$USER"
```

Some software won't even look at the [libpq environment variables][].
Here's what you need to tell it:

- Host: the absolute path to the sockets directory (`$PGDATA/sockets`)
- Port: `5432`
- Database: `postgres`
- Username: the same as your unix username (`$USER`)
- Password: none

[libpq environment variables]: https://www.postgresql.org/docs/current/static/libpq-envars.html

## Other things

- You could add /usr/lib/postgresql/10/bin/ to your $PATH so you don't have to
  type it out to use pg_ctl
- You could put a symlink to /usr/lib/postgresql/10/bin/pg_sql somewhere that's
  already on your $PATH
- If you don't like environment variables, you can use explicit options like -D
  to specify the path to PostgreSQL's data directory ($PGDATA)
- You can tell it to use a logfile if you like.
