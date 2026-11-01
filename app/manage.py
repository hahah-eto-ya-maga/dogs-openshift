import sys
from app import database, initialize, query

if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    if command == 'init':
        initialize()
        print('Schema and demo data are ready.')
    elif command == 'report':
        with database() as conn:
            print(query(conn, 'SELECT status, count(*) AS count FROM dogs GROUP BY status'), flush=True)
    else:
        raise SystemExit('Usage: python -m app.manage init|report')
