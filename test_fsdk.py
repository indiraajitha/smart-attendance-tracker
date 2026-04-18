import fsdk
from fsdk import FSDK

license_key = "fVrFCzYC5wOtEVspKM/zfLWVcSIZA4RNqx74s+QngdvRiCC3z7MHlSf2w3+OUyAZkTFeD4kSpfVPcRVIqAKWUZzJG975b/P4HNNzpl11edXGIyGrTO/DImoZksDSRs6wktvgr8lnNCB5IukIPV5j/jBKlgL5aqiwSfyCR8UdC9s=" # Your provided key

try:
    print("Attempting to activate FSDK library...")
    FSDK.ActivateLibrary(license_key)
    print("Attempting to initialize FSDK...")
    FSDK.Initialize()
    print("FSDK Initialization successful!")
    print("License info:", FSDK.GetLicenseInfo())
except Exception as e:
    print(f"FSDK Initialization FAILED: {e}")
except:
    print("FSDK Initialization FAILED with an unknown critical error.")
finally:
    print("Attempting to finalize FSDK...")
    FSDK.Finalize() # Clean up