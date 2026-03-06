import logging
import os
import multiprocessing
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.dialects.postgresql import insert as pg_insert
from src.emby.client import EmbyClient
from src.emby.models import MediaInfo
from src.database.db import db, Media, SyncLog

logger = logging.getLogger(__name__)
BATCH_SIZE = 1000

def _get_max_workers(app) -> int:
    try:
        with app.app_context():
            pg_max = int(db.session.execute(
                db.text('SHOW max_connections')
            ).scalar())
            workers = max(int(pg_max * 0.8), 8)
            workers = min(workers, multiprocessing.cpu_count() * 4)
            logger.info(f"PG max_connections={pg_max}, workers={workers}")
            return workers
    except Exception:
        return 16


class EmbySyncService:
    def __init__(self, app=None):
        self.app = app

    def _get_client(self, pool_maxsize: int = 32) -> EmbyClient:
        return EmbyClient(
            os.getenv('EMBY_SERVER_URL', 'http://localhost:8096'),
            os.getenv('EMBY_API_KEY', ''),
            pool_maxsize=pool_maxsize,
        )

    def sync_all_libraries(self):
        from src.main import create_app
        app = create_app()

        max_workers = _get_max_workers(app)
        client = self._get_client(pool_maxsize=max_workers)

        libraries = client.get_libraries()
        if not libraries:
            logger.warning("No libraries found")
            self._write_sync_log('error', 0, 'No libraries found')
            return

        total  = 0
        errors = []

        all_tasks = []
        with ThreadPoolExecutor(max_workers=min(len(libraries), max_workers)) as executor:
            size_futures = {
                executor.submit(self._get_library_total, client, lib): lib
                for lib in libraries
            }
            for future in as_completed(size_futures):
                lib = size_futures[future]
                try:
                    total_count = future.result()
                    batches = (total_count + BATCH_SIZE - 1) // BATCH_SIZE
                    for i in range(batches):
                        all_tasks.append((lib, i * BATCH_SIZE))
                    logger.info(f"  {lib.get('Name')}: {total_count}条/{batches}批")
                except Exception as e:
                    errors.append(f"{lib.get('Name')}: {e}")

        logger.info(f"Total: {len(all_tasks)} batches, {max_workers} workers")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            batch_futures = {
                executor.submit(self._sync_batch_safe, app, client, lib, start):
                    (lib.get('Name', ''), start)
                for lib, start in all_tasks
            }
            for future in as_completed(batch_futures):
                lib_name, start = batch_futures[future]
                try:
                    total += future.result()
                except Exception as e:
                    errors.append(f"{lib_name}@{start}: {e}")
                    logger.error(f"X {lib_name}@{start}: {e}")

        error_msg = '; '.join(errors) if errors else None
        self._write_sync_log(app, 'success' if not errors else 'partial', total, error_msg)
        logger.info(f"Sync complete: {total} items, {len(errors)} errors, workers={max_workers}")

    def _get_library_total(self, client, lib):
        lib_id = lib.get('Guid') or lib.get('ItemId') or lib.get('Id', '')
        result = client.get_items(lib_id, limit=1, start_index=0)
        return result.get('TotalRecordCount', 0)

    def _sync_batch_safe(self, app, client, lib, start):
        with app.app_context():
            return self._sync_batch(client, lib, start)

    def _sync_batch(self, client, lib, start):
        lib_id   = lib.get('Guid') or lib.get('ItemId') or lib.get('Id', '')
        lib_name = lib.get('Name', '')

        result = client.get_items(lib_id, limit=BATCH_SIZE, start_index=start)
        items  = result.get('Items', [])
        if not items:
            return 0

        now  = datetime.utcnow()
        rows = []
        for item in items:
            try:
                info = MediaInfo.from_emby_item(item, lib_id, lib_name)
                rows.append({
                    'emby_id':    info.emby_id,
                    'title':      info.title,
                    'media_type': info.media_type,
                    'path':       info.path,
                    'size':       info.size,
                    'duration':   info.duration,
                    'year':       info.year,
                    'created_at': now,
                    'updated_at': now,
                })
            except Exception as e:
                logger.warning(f"Parse {item.get('Id')}: {e}")

        if not rows:
            return 0

        stmt = pg_insert(Media).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=['emby_id'],
            set_={
                'title':      stmt.excluded.title,
                'media_type': stmt.excluded.media_type,
                'path':       stmt.excluded.path,
                'size':       stmt.excluded.size,
                'duration':   stmt.excluded.duration,
                'year':       stmt.excluded.year,
                'updated_at': stmt.excluded.updated_at,
            }
        )
        db.session.execute(stmt)
        db.session.commit()
        logger.info(f"  {lib_name}@{start}: {len(rows)}条")
        return len(rows)

    def _write_sync_log(self, app, status, items_synced, error_message=None):
        try:
            with app.app_context():
                db.session.add(SyncLog(
                    status=status,
                    items_synced=items_synced,
                    error_message=error_message
                ))
                db.session.commit()
        except Exception as e:
            logger.error(f"Sync log error: {e}")