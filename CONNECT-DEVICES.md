# Connect Devices

LocalLens can discover a phone on the same private Wi-Fi, pair with your approval,
and display device resources. Desktop CPU and GPU benchmarks still run locally.
Phone compute is unavailable in this preview.

## Native Android companion

1. Build and install the Android companion using the [Android guide](android/companion/README.md).
2. Open the companion and enable discovery. On Windows, open **Connect Devices** and choose **Add device**.
3. Select your phone and compare the request-specific verification code on both screens.
4. Approve on the phone and confirm the match on Windows. You can revoke trust from either device.

If discovery is blocked, enter the phone's Wi-Fi address manually. Read the
[architecture notes](DEVICES-ARCHITECTURE.md) for the pairing and trust flow.

## Termux pairing fallback

Copy `companion.py` and `connectnet.py` to the same folder in Termux. Install
the required tools and start the companion:

```sh
pkg install python openssl-tool
python companion.py --name 'Android companion'
```

In LocalLens, select the discovered companion, compare its complete certificate
fingerprint with the one printed by Termux, then enter the displayed pairing
code. Approve the matching request in Termux. Use `revoke-all` to end all
pairings or `quit` to stop discovery and exit. Shut down any older Termux compute
session before starting this version.

## Network and results

Use pairing on a trusted private Wi-Fi network. Keep router port forwarding off.
Discovery announcements are untrusted. Certificate verification and phone
approval are required before device details are read. A peer on the same Wi-Fi
can disrupt discovery or pairing, so stop discovery when you are done.

Connection reports and older experiment results stay in the local journal.
Exports can contain device details. Review them before sharing.
