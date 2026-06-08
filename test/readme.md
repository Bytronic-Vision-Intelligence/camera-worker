# test

This folder contains automated tests for the Example Camera Worker.

## Current status

- `Test_dummy.py` is a placeholder test file.
- It currently contains a minimal sanity check and can be extended with real unit tests.

## Running tests

From the repository root:

```powershell
pytest test
```

## Recommended next steps

- Add tests for configuration loading in `app/Dependencies/loadConfig.py`.
- Add tests for camera selection and message handling.
- Add integration tests for MQTT publish/subscribe behavior.
