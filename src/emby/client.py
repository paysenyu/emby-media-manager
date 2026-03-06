"""
Emby API Client Module
"""
import os
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

def _make_session(pool_connections: int = 4, pool_maxsize: int = 32) -> requests.Session:
    """创建带连接池和重试的 Session"""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize,
        max_retries=retry,
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


class EmbyClient:
    def __init__(self, server_url: str, api_key: str, pool_maxsize: int = 32):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.user_id = os.getenv('EMBY_USER_ID', '')
        # pool_maxsize 与并发线程数匹配，避免 "Connection pool is full" 警告
        self.session = _make_session(pool_maxsize=pool_maxsize)

    def _get_headers(self) -> Dict[str, str]:
        return {
            'X-MediaBrowser-Token': self.api_key,
            'User-Agent': 'Emby-Media-Manager/1.0'
        }

    def test_connection(self) -> bool:
        try:
            url = f"{self.server_url}/System/Info"
            response = self.session.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            logger.info("Successfully connected to Emby server")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Emby server: {e}")
            return False

    def get_libraries(self) -> List[Dict[str, Any]]:
        """获取媒体库列表，返回 [{Id, Name, CollectionType}, ...]"""
        try:
            url = f"{self.server_url}/Users/{self.user_id}/Views"
            response = self.session.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            data = response.json()
            items = data.get('Items', [])
            logger.info(f"Retrieved {len(items)} libraries from Emby server")
            return items
        except Exception as e:
            logger.error(f"Failed to get libraries: {e}")
            return []

    def get_items(
        self,
        library_id: str,
        limit: int = 500,
        start_index: int = 0,
        min_date_last_saved: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取媒体库内的媒体项"""
        try:
            url = (
                f"{self.server_url}/Users/{self.user_id}/Items"
                f"?ParentId={library_id}"
                f"&Limit={limit}"
                f"&StartIndex={start_index}"
                f"&Recursive=true"
                f"&Fields=Path,MediaSources,RunTimeTicks,ProductionYear,Overview"
                f"&IncludeItemTypes=Movie,Series,Episode,Audio,MusicAlbum"
            )
            if min_date_last_saved:
                url += f"&MinDateLastSaved={min_date_last_saved}"
            response = self.session.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get items from library {library_id}: {e}")
            return {}

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.server_url}/Users/{self.user_id}/Items/{item_id}"
            response = self.session.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get item details for {item_id}: {e}")
            return None

    def get_multi_version_items(self, limit: int = 500) -> List[Dict[str, Any]]:
        """获取所有有多个版本的媒体（MediaSources数组长度>1）"""
        try:
            url = (
                f"{self.server_url}/Users/{self.user_id}/Items"
                f"?GroupByPresentationUniqueKey=true"
                f"&Recursive=true"
                f"&Fields=MediaSources,Path,RunTimeTicks,ProductionYear,Overview"
                f"&IncludeItemTypes=Movie,Series"
                f"&Limit={limit}"
            )
            response = self.session.get(url, headers=self._get_headers(), timeout=60)
            response.raise_for_status()
            data = response.json()
            items = data.get('Items', [])
            multi_version = [item for item in items if len(item.get('MediaSources', [])) > 1]
            logger.info(f"Found {len(multi_version)} multi-version items out of {len(items)} total")
            return multi_version
        except Exception as e:
            logger.error(f"Failed to get multi-version items: {e}")
            return []

    def delete_version(self, item_id: str, version_ids: List[str]) -> bool:
        """调用神医 DeleteVersion 接口删除指定版本"""
        try:
            url = f"{self.server_url}/Items/{item_id}/DeleteVersion"
            response = self.session.post(
                url,
                headers=self._get_headers(),
                json={"Ids": version_ids},
                timeout=30,
            )
            response.raise_for_status()
            logger.info(f"Deleted versions {version_ids} from item {item_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete versions {version_ids} from item {item_id}: {e}")
            return False
