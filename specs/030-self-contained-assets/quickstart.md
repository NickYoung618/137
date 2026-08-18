# Quickstart: Portable Mac Replay Assets

After implementation, the server reviewer builds one Git-external archive from the reviewed 029 configuration and locked assets. The Mac operator then needs only the specified Git revision and that archive.

```bash
tar -xzf slot-pose-030-portable.tar.gz
python tools/verify_slot_pose_portable_bundle.py \
  --bundle-dir slot-pose-030-portable
```

The verifier prints the effective configuration SHA-256. Pass the extracted bundle's `config.json` to the existing replay command from any current working directory.

Expected safety behavior:

- Moving the extracted directory remains valid.
- Editing/deleting either asset fails verification and adapter initialization.
- No `/home/ubuntu`, gyj, or yyh directory is created or accessed on Mac.
- Replay remains diagnostic only; PLC stays unauthorized and null.

The final evidence handoff will replace the generic archive name above with the exact external path, archive SHA-256, branch, and commit.
