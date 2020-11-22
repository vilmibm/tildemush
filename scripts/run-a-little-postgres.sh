#!/bin/bash

# default options
destroy_existing=0

# local variables
initialized=0

function helptext {
	cat <<EOH
Available Options:
	-x
		destroy the existing pgdata directory and start afresh

	-h
		shows this help text
EOH
	exit
}

while getopts "xh" opt; do
	case $opt in
		x)
			destroy_existing=1
			;;
		\?)
			helptext
			;;
		h)
			helptext
			;;
	esac
done

set -xe

export PATH="/usr/local/Cellar/postgresql/10.5/bin/:$PATH"

export PGDATA="$PWD/pgdata"
export PGHOST="$PGDATA/sockets"
export PGDATABASE="postgres"
export PGUSER="$USER"

if [ $destroy_existing -eq 1 ]; then 
	rm -rf $PGDATA
fi

if [ ! -d "$PGDATA" ]; then
	pg_ctl init

	mkdir -p "$PGDATA/sockets"

	cat >> "$PGDATA/postgresql.conf" << EOF
unix_socket_directories = 'sockets'
listen_addresses = ''
EOF

	initialized=1
fi

pg_ctl start

function cleanup {
	set -x

	pg_ctl stop
}

trap 'cleanup' SIGINT

if [ $initialized -eq 1 ]; then
	createdb postgres_test
fi

cat > pgconfig.sh <<EOF

export PGHOST=$PGHOST
export PGDATABASE=$PGDATABASE
export PGUSER=$PGUSER

EOF

set +x

echo
echo \`source pgconfig.sh\` to get useful environment variables set up in other shells.
echo

while true; do
	echo "a little postgres running... (ctrl-c to stop)"
	sleep 60
done

