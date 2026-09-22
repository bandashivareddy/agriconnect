"""Apply reviewed migrations only to explicitly selected local development/test DBs."""
import argparse
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from alembic.config import Config
from alembic import command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=['test','development'], required=True)
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[1]
    load_dotenv(backend / '.env')
    normal = os.environ['DB_NAME']
    test = os.environ.get('AGRI_TEST_DB_NAME', '')
    if not test or test == normal or 'test' not in test.lower():
        raise RuntimeError('A distinct test-named AGRI_TEST_DB_NAME is required.')
    if os.environ['DB_HOST'] not in ('localhost','127.0.0.1','::1'):
        raise RuntimeError('This helper only migrates local development/test databases.')
    target = test if args.target == 'test' else normal
    os.environ['DB_NAME'] = target
    engine = create_engine(URL.create('postgresql+psycopg', username=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']), database=target))
    config = Config(str(backend / 'alembic.ini'))
    config.set_main_option('script_location', str(backend / 'alembic'))
    with engine.connect() as c:
        assert c.execute(text('SELECT current_database()')).scalar_one() == target
        tables = set(c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
        revisions = list(c.execute(text('SELECT version_num FROM alembic_version')).scalars()) if 'alembic_version' in tables else []
        if not revisions and tables:
            # Historical test DB was made by schema-only restore, without Alembic tracking.
            # Compare its full structural signature to the tracked development baseline.
            if args.target != 'test':
                raise RuntimeError('Refusing to stamp an untracked development database.')
            reference_engine = create_engine(engine.url.set(database=normal))
            signature_sql = """SELECT table_name,column_name,data_type,is_nullable,character_maximum_length,numeric_precision,numeric_scale
              FROM information_schema.columns WHERE table_schema='public' AND table_name<>'alembic_version'
              ORDER BY table_name,ordinal_position"""
            constraints_sql = """SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint
              WHERE connamespace='public'::regnamespace AND conrelid::regclass::text<>'alembic_version' ORDER BY 1,2"""
            with reference_engine.connect() as reference:
                if list(reference.execute(text('SELECT version_num FROM alembic_version')).scalars()) != ['8b213a901def']:
                    raise RuntimeError('Untracked test DB must be compared before development advances beyond the baseline.')
                for query in (signature_sql, constraints_sql):
                    def normalize(result):
                        normalized = []
                        for row in result:
                            values = list(row)
                            # pg_dump restore can place equivalent text casts on each
                            # array member rather than on the entire varchar array.
                            if query == constraints_sql and ' = ANY (' in values[2]:
                                value = values[2].replace('::character varying', '').replace('::text[]', '').replace('::text', '')
                                values[2] = re.sub(r'[()\s]', '', value)
                            normalized.append(tuple(values))
                        return normalized
                    if normalize(c.execute(text(query)).all()) != normalize(reference.execute(text(query)).all()):
                        raise RuntimeError('Test/development schemas differ; refusing automatic test baseline stamp.')
            reference_engine.dispose()
            c.rollback()
            command.stamp(config, '8b213a901def')
    command.upgrade(config, 'head')
    with engine.connect() as c:
        print(f"Verified {args.target} database migration: " + ','.join(c.execute(text('SELECT version_num FROM alembic_version')).scalars()))
    engine.dispose()


if __name__ == '__main__':
    main()
