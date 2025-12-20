import os
import sys
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

async def verify_gemini():
    print("\n[1/2] Verifying Gemini API Key...")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ FAIL: GEMINI_API_KEY not found in environment.")
        return False
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # Try a list of known models
        models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
        last_error = None
        
        for model_name in models_to_try:
            print(f"   Trying model: {model_name}...", end=" ")
            try:
                model = genai.GenerativeModel(model_name)
                response = await model.generate_content_async("Reply with 'OK'")
                if response.text:
                    print(f"✅ WORKS")
                    return True
            except Exception as e:
                print(f"❌ Failed ({e})")
                last_error = e
                
        if last_error:
            print("\n   ⚠️  listing available models for valid API key:")
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        print(f"      - {m.name}")
            except Exception as e:
                print(f"      (Could not list models: {e})")
                
        print(f"❌ FAIL: All Gemini models failed.")
        return False
    except Exception as e:
        print(f"❌ FAIL: Gemini Error: {e}")
        return False

async def verify_google_tts():
    print("\n[2/2] Verifying Google TTS API Key...")
    api_key = os.getenv("GOOGLE_TTS_API_KEY")
    if not api_key:
        print("❌ FAIL: GOOGLE_TTS_API_KEY not found in environment.")
        return False
        
    try:
        import httpx
        url = f"https://texttospeech.googleapis.com/v1/voices?key={api_key}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                print(f"✅ SUCCESS: Google TTS API accepted key (Voices list retrieved).")
                return True
            else:
                print(f"❌ FAIL: Google TTS returned {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"❌ FAIL: Google TTS Error: {e}")
        return False

async def main():
    load_dotenv()
    print("--- API Key Verification ---")
    
    gemini_ok = await verify_gemini()
    tts_ok = await verify_google_tts()
    
    print("\n--- Summary ---")
    if gemini_ok and tts_ok:
        print("🎉 All systems GO! You are ready to generate episodes.")
    else:
        print("⚠️ Some keys are missing or invalid. Please check your .env file.")

if __name__ == "__main__":
    asyncio.run(main())
