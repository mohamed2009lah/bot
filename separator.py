import os, logging, asyncio
logger = logging.getLogger(__name__)

class AudioSeparator:
    def __init__(self):
        self.temp = "temp_audio"
        os.makedirs(self.temp, exist_ok=True)
    async def separate(self, audio_path):
        out_dir = os.path.join(self.temp, f"sep_{os.urandom(4).hex()}")
        os.makedirs(out_dir, exist_ok=True)
        cmd = ['spleeter','separate','-p','spleeter:2stems','-o',out_dir,audio_path]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            _, stderr = await proc.communicate()
            if proc.returncode!=0: return None, f"❌ فشل: {stderr.decode()}"
            result = {}
            for root,_,files in os.walk(out_dir):
                for f in files:
                    if 'vocals' in f: result['vocals'] = os.path.join(root,f)
                    elif 'accompaniment' in f: result['music'] = os.path.join(root,f)
            return result, None
        except Exception as e:
            logger.error(f"Separator: {e}"); return None, str(e)