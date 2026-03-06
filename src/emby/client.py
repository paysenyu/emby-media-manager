"""
Emby API Client Module
"""
import os
import requests
import logging
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class EmbyClient:
    def __init__(self, server_url: str, api_key: str):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.user_id = os.getenv('EMBY_USER_ID', '')
        self.session = requests.Session()

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

    def get_items(self, library_id: str, limit: int = 500, start_index: int = 0) -> Dict[str, Any]:
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
