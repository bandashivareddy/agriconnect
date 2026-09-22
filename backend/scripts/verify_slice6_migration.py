"""Guarded local Slice 6 migration with original-column integrity comparison."""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from alembic import command
from alembic.config import Config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=['test', 'development'], required=True)
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[1]
    load_dotenv(backend / '.env')
    normal, test = os.environ['DB_NAME'], os.environ['AGRI_TEST_DB_NAME']
    assert normal != test and 'test' in test.lower()
    assert os.environ['DB_HOST'] in ('localhost', '127.0.0.1', '::1')
    target = test if args.target == 'test' else normal
    os.environ['DB_NAME'] = target
    engine = create_engine(URL.create('postgresql+psycopg', username=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']), database=target))
    def quote(value):
        return '"' + value.replace('"', '""') + '"'
    with engine.connect() as c:
        assert c.execute(text('SELECT current_database()')).scalar_one() == target
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'c7f216a2e485'
        columns = {}
        for table, column in c.execute(text("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND table_name<>'alembic_version' ORDER BY table_name,ordinal_position")):
            columns.setdefault(table, []).append(column)
        queries = {table: 'SELECT count(*),md5(coalesce(string_agg(row_data,\'\' ORDER BY row_data),\'\')) FROM (SELECT row_to_json(r)::text row_data FROM (SELECT ' + ','.join(map(quote, cols)) + ' FROM public.' + quote(table) + ') r) data' for table, cols in columns.items()}
        before = {table: tuple(c.execute(text(q)).one()) for table, q in queries.items()}
    config = Config(str(backend / 'alembic.ini'))
    config.set_main_option('script_location', str(backend / 'alembic'))
    command.upgrade(config, 'd8a327b3f596')
    if args.target == 'test':
        command.downgrade(config, 'c7f216a2e485')
        command.upgrade(config, 'd8a327b3f596')
        print('Guarded test downgrade/reapply passed.')
    with engine.connect() as c:
        after = {table: tuple(c.execute(text(q)).one()) for table, q in queries.items()}
        assert before == after, 'Original-column data changed.'
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'd8a327b3f596'
        assert not c.execute(text('SELECT EXISTS(SELECT 1 FROM farm_crops WHERE expected_planting_on IS NOT NULL) OR EXISTS(SELECT 1 FROM sop_tasks WHERE phase IS NOT NULL) OR EXISTS(SELECT 1 FROM crop_tasks WHERE phase IS NOT NULL) OR EXISTS(SELECT 1 FROM crop_cycle_plans WHERE season_start_snapshot IS NOT NULL OR expected_harvest_snapshot IS NOT NULL)')).scalar_one()
    print(f'{args.target}: d8a327b3f596; all {len(before)} existing tables retain counts and original-column fingerprints; all added fields NULL.')
    engine.dispose()


if __name__ == '__main__':
    main()
