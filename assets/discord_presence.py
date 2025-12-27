from pypresence import Presence
import datetime as dt


class RichPresenceManager:
    def __init__(self):
        self.client_id = "1144714449563955302"
        self.rpc = None
        self.running = False

    def start_presence(self):
        if not self.running:
            # Skip Discord presence in Docker/container environments
            import os
            if os.getenv('DISABLE_DISCORD_PRESENCE', '').lower() in ('1', 'true', 'yes') or \
               os.path.exists('/.dockerenv') or \
               os.getenv('DOCKER_CONTAINER', '').lower() in ('1', 'true', 'yes'):
                return
            
            self.running = True
            self.rpc = Presence(self.client_id)
            try:
                self.rpc.connect()
                self.update_presence()
            except KeyboardInterrupt as error:
                print(error)
                self.rpc = None
                self.running = False
            except Exception as error:
                # Silently fail in container environments or when Discord is not available
                import os
                error_str = str(error).lower()
                is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER')
                is_discord_error = 'discord' in error_str or 'event loop' in error_str or 'not found' in error_str
                
                if is_docker or is_discord_error:
                    # Silently ignore in Docker or when Discord is not available
                    pass
                else:
                    print(f"An error occurred connecting to Discord: {error}")
                self.rpc = None
                self.running = False

    def update_presence(self):
        if self.rpc:
            self.rpc.update(
                state="applio.org",
                details="Open ecosystem for voice cloning",
                buttons=[
                    {"label": "Home", "url": "https://applio.org"},
                    {"label": "Download", "url": "https://applio.org/products/applio"},
                ],
                large_image="logo",
                large_text="Experimenting with applio",
                start=dt.datetime.now().timestamp(),
            )

    def stop_presence(self):
        self.running = False
        if self.rpc:
            self.rpc.close()
            self.rpc = None


RPCManager = RichPresenceManager()
