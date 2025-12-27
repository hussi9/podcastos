"""
Google AI Stack Version Monitor & Auto-Upgrader
Keeps your system updated with latest Google AI releases
"""
import os
import asyncio
import json
import subprocess
from typing import Dict, List
from datetime import datetime
from pathlib import Path
import aiohttp
from packaging import version


class GoogleAIVersionMonitor:
    """
    Monitor Google AI releases and auto-upgrade
    - Checks for new Gemini models
    - Monitors ADK updates
    - Tracks Google Cloud library versions
    - Can auto-upgrade with your approval
    """
    
    def __init__(self, auto_upgrade: bool = False):
        """
        Args:
            auto_upgrade: If True, automatically upgrade (use with caution!)
        """
        self.auto_upgrade = auto_upgrade
        self.version_file = Path("config/google_ai_versions.json")
        self.version_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize version tracking
        self.current_versions = self._load_current_versions()
    
    def _load_current_versions(self) -> Dict:
        """Load currently installed versions"""
        if self.version_file.exists():
            with open(self.version_file) as f:
                return json.load(f)
        return {
            "last_checked": None,
            "packages": {},
            "models": {}
        }
    
    def _save_current_versions(self):
        """Save current versions to file"""
        with open(self.version_file, 'w') as f:
            json.dump(self.current_versions, f, indent=2)
    
    async def check_for_updates(self) -> Dict:
        """
        Check for available updates
        
        Returns:
            {
                "packages": [
                    {"name": "google-genai", "current": "1.0.0", "latest": "1.1.0"},
                    ...
                ],
                "models": [
                    {"name": "gemini-2.0-flash-thinking-exp-1219", "released": "2024-12-19"},
                    ...
                ],
                "needs_update": True/False
            }
        """
        
        print("🔍 Checking for Google AI updates...")
        
        updates = {
            "packages": [],
            "models": [],
            "needs_update": False
        }
        
        # Check package versions
        package_updates = await self._check_package_updates()
        updates["packages"] = package_updates
        
        # Check for new Gemini models
        model_updates = await self._check_new_models()
        updates["models"] = model_updates
        
        # Determine if updates are needed
        updates["needs_update"] = len(package_updates) > 0 or len(model_updates) > 0
        
        # Update tracking
        self.current_versions["last_checked"] = datetime.utcnow().isoformat()
        self._save_current_versions()
        
        return updates
    
    async def _check_package_updates(self) -> List[Dict]:
        """Check PyPI for package updates"""
        
        packages_to_check = [
            "google-genai",
            "google-adk",
            "google-generativeai",
            "google-cloud-texttospeech",
            "google-cloud-storage"
        ]
        
        updates = []
        
        for package in packages_to_check:
            try:
                # Get installed version
                result = subprocess.run(
                    ["pip", "show", package],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    continue
                
                # Parse version
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        current_version = line.split(':', 1)[1].strip()
                        break
                
                # Check PyPI for latest
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://pypi.org/pypi/{package}/json") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            latest_version = data['info']['version']
                            
                            # Compare versions
                            if version.parse(latest_version) > version.parse(current_version):
                                updates.append({
                                    "name": package,
                                    "current": current_version,
                                    "latest": latest_version,
                                    "upgrade_command": f"pip install --upgrade {package}=={latest_version}"
                                })
                                print(f"  📦 {package}: {current_version} → {latest_version}")
            
            except Exception as e:
                print(f"  ⚠️  Error checking {package}: {e}")
        
        return updates
    
    async def _check_new_models(self) -> List[Dict]:
        """Check for new Gemini models"""
        
        from google import genai
        
        try:
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            
            # List all available models
            models = client.models.list()
            
            new_models = []
            known_models = self.current_versions.get("models", {})
            
            for model in models:
                model_id = model.name
                
                # Check if this is a new model
                if model_id not in known_models:
                    # Check if it's a Gemini 2.0 or newer model
                    if "gemini-2" in model_id.lower() or "gemini-3" in model_id.lower():
                        new_models.append({
                            "name": model_id,
                            "description": getattr(model, 'description', 'No description'),
                            "discovered": datetime.utcnow().isoformat()
                        })
                        print(f"  🆕 New model: {model_id}")
                        
                        # Track it
                        known_models[model_id] = {
                            "discovered": datetime.utcnow().isoformat()
                        }
            
            # Update tracking
            self.current_versions["models"] = known_models
            
            return new_models
            
        except Exception as e:
            print(f"  ⚠️  Error checking models: {e}")
            return []
    
    async def upgrade_system(self, updates: Dict) -> Dict:
        """
        Upgrade packages and update configurations
        
        Args:
            updates: Result from check_for_updates()
        
        Returns:
            {"success": True/False, "upgraded": [...], "failed": [...]}
        """
        
        if not updates["needs_update"]:
            print("✅ System is up to date!")
            return {"success": True, "upgraded": [], "failed": []}
        
        print("\n🚀 Starting system upgrade...")
        
        upgraded = []
        failed = []
        
        # Upgrade packages
        for pkg_update in updates["packages"]:
            try:
                print(f"\n  📦 Upgrading {pkg_update['name']}...")
                result = subprocess.run(
                    ["pip", "install", "--upgrade", f"{pkg_update['name']}=={pkg_update['latest']}"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    upgraded.append(pkg_update['name'])
                    print(f"  ✅ {pkg_update['name']} upgraded to {pkg_update['latest']}")
                    
                    # Update tracking
                    self.current_versions["packages"][pkg_update['name']] = {
                        "version": pkg_update['latest'],
                        "upgraded_at": datetime.utcnow().isoformat()
                    }
                else:
                    failed.append({
                        "name": pkg_update['name'],
                        "error": result.stderr
                    })
                    print(f"  ❌ Failed to upgrade {pkg_update['name']}")
            
            except Exception as e:
                failed.append({
                    "name": pkg_update['name'],
                    "error": str(e)
                })
                print(f"  ❌ Error upgrading {pkg_update['name']}: {e}")
        
        # Update model configurations
        if updates["models"]:
            await self._update_model_configs(updates["models"])
        
        # Save updated versions
        self.current_versions["last_upgraded"] = datetime.utcnow().isoformat()
        self._save_current_versions()
        
        print("\n" + "="*60)
        if len(failed) == 0:
            print("✨ System upgrade complete!")
        else:
            print(f"⚠️  Upgrade completed with {len(failed)} failures")
        print("="*60)
        
        return {
            "success": len(failed) == 0,
            "upgraded": upgraded,
            "failed": failed
        }
    
    async def _update_model_configs(self, new_models: List[Dict]):
        """Update code to use latest models"""
        
        print("\n  🔧 Updating model configurations...")
        
        # Find the latest "thinking" model
        thinking_models = [m for m in new_models if "thinking" in m["name"].lower()]
        if thinking_models:
            latest_thinking = thinking_models[0]["name"]
            print(f"  💡 Latest thinking model: {latest_thinking}")
            
            # Could auto-update config files here
            # For now, just inform the user
            print(f"  📝 Update newsletter_generator_thinking.py to use: {latest_thinking}")
        
        # Find latest flash model
        flash_models = [m for m in new_models if "flash" in m["name"].lower() and "thinking" not in m["name"].lower()]
        if flash_models:
            latest_flash = flash_models[0]["name"]
            print(f"  ⚡ Latest flash model: {latest_flash}")
            print(f"  📝 Update research/script agents to use: {latest_flash}")
    
    async def run_auto_check(self):
        """Run automated check (for cron/scheduler)"""
        
        print("🤖 Running automated update check...")
        updates = await self.check_for_updates()
        
        if updates["needs_update"]:
            print(f"\n⚡ {len(updates['packages'])} package updates available")
            print(f"⚡ {len(updates['models'])} new models available")
            
            if self.auto_upgrade:
                print("\n🚀 Auto-upgrade enabled, upgrading now...")
                result = await self.upgrade_system(updates)
                return result
            else:
                print("\n💡 To upgrade, run:")
                print("   python -m scripts.upgrade_google_ai")
                return {"needs_manual_upgrade": True, "updates": updates}
        else:
            print("✅ System is up to date!")
            return {"needs_manual_upgrade": False}


# CLI Interface
async def main():
    """CLI for version monitoring"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Google AI Stack Version Monitor")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for available updates"
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Upgrade to latest versions"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Enable auto-upgrade (use with caution!)"
    )
    
    args = parser.parse_args()
    
    monitor = GoogleAIVersionMonitor(auto_upgrade=args.auto)
    
    if args.check or (not args.upgrade):
        # Default: check for updates
        updates = await monitor.check_for_updates()
        
        if updates["needs_update"]:
            print("\n📋 AVAILABLE UPDATES:")
            print("="*60)
            
            if updates["packages"]:
                print("\nPackages:")
                for pkg in updates["packages"]:
                    print(f"  • {pkg['name']}: {pkg['current']} → {pkg['latest']}")
            
            if updates["models"]:
                print("\nNew Models:")
                for model in updates["models"]:
                    print(f"  • {model['name']}")
            
            print("\n💡 To upgrade, run:")
            print("   python -m scripts.upgrade_google_ai --upgrade")
        else:
            print("\n✅ System is up to date!")
    
    elif args.upgrade:
        # Upgrade system
        updates = await monitor.check_for_updates()
        if updates["needs_update"]:
            result = await monitor.upgrade_system(updates)
            
            if result["success"]:
                print("\n✨ Upgrade successful!")
            else:
                print(f"\n⚠️  Upgrade completed with errors:")
                for failure in result["failed"]:
                    print(f"  • {failure['name']}: {failure['error']}")


if __name__ == "__main__":
    asyncio.run(main())
