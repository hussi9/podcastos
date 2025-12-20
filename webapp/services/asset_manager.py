import os
import shutil
from pathlib import Path
from typing import Optional, Union

class AssetManager:
    """
    Abstracts media asset storage.
    Currently implements local filesystem storage, but designed to support
    S3/Cloud Storage in the future without changing client code.
    """
    
    def __init__(self, base_path: Union[str, Path]):
        self.base_path = Path(base_path)
        self.audio_dir = self.base_path / 'audio'
        self.images_dir = self.base_path / 'images'
        
        # Ensure directories exist
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def save_audio(self, source_path: Union[str, Path], filename: str) -> str:
        """
        Saves an audio file to the storage.
        Returns the relative path or URL to the asset.
        """
        target_path = self.audio_dir / filename
        shutil.copy2(source_path, target_path)
        # In a real S3 implementation, this would return the S3 key or public URL
        return filename

    def get_audio_path(self, filename: str) -> Path:
        """
        Returns the local filesystem path for an audio file.
        In S3 mode, this might download the file to a temp location.
        """
        return self.audio_dir / filename

    def delete_audio(self, filename: str) -> bool:
        """Deletes an audio file."""
        try:
            target_path = self.audio_dir / filename
            if target_path.exists():
                target_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting asset {filename}: {e}")
            return False

# Singleton instance for the app
# In production, receive config from env to decide storage backend
OUTPUT_DIR = Path(__file__).parent.parent.parent / 'output'
asset_manager = AssetManager(OUTPUT_DIR)
