# POS runtime boundary
The Python POS adapter calls server commands. Hardware adapters are isolated under `hardware/`.
A production Flet UI should bind scan/cart/payment/receipt events to these command contracts.
