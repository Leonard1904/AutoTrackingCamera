from config import SystemConfig
from core.app import DualCameraTrackingApp

def main():
    config = SystemConfig()
    app = DualCameraTrackingApp(config)
    
    if app.initialize():
        app.run()
    else:
        print("\n  Initialization failed\n")

if __name__ == "__main__":
    main()