# app/board/
- `frontend.py` (P2): capture -> backend (`fpga` or `arm`) -> VAD gate -> MQTT. Tested with the ARM backend.
- `dma_lib.py`, `dma_test.py` (P1): FPGA backend. Untested: register offsets are placeholders until the HLS block exists.
- `voice.conf`: default settings. Overrides and the MQTT password go in `/data/voice.conf` on the board.
- `features.py` is imported from `common/` (the PetaLinux recipe installs a copy next to `frontend.py`).
