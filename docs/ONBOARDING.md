# Onboarding facts for a later UI

Recorded 2026-10-16 from the τ² telecom adapter. Not a UI. These are the questions an onboarding flow should ask, and the answers this repo already knows for telecom.

## Questions to ask

1. Which benchmark and domain? Today: τ²-bench, domain `telecom`. Text only. Voice is out of scope.
2. Which tool surface may the agent call? Which actions belong to the user?
3. What may the loop edit? System prompt and playbook bullets. Domain policy, tool code, and the scorer stay protected.
4. Which split is this run allowed to see? `opt` and `val` during improvement. `select` only for a later finalist audit. `test` stays unread until freeze.
5. What is the dollar cap, the model, and the seed?

## Telecom answers

τ² gives the assistant one tool list and the user simulator another. The policy document describes both. The model was calling user-device names (`toggle_airplane_mode`, `run_speed_test`, `disconnect_vpn`) as if they were its own tools. Those calls return "tool not found". The assistant must ask the user to do them.

**Agent tools** (carrier account; the assistant may call these):

- `get_customer_by_phone`, `get_customer_by_id`, `get_customer_by_name`
- `get_details_by_id`, `get_bills_for_customer`, `get_data_usage`
- `suspend_line`, `resume_line`, `send_payment_request`
- `enable_roaming`, `disable_roaming`, `refuel_data`
- `transfer_to_human_agents`

**User tools** (the phone; ask the user, do not call):

- Status and network: `check_status_bar`, `check_network_status`, `check_network_mode_preference`, `set_network_mode_preference`, `run_speed_test`
- Radio and SIM: `toggle_airplane_mode`, `check_sim_status`, `reseat_sim_card`, `toggle_data`, `toggle_roaming`, `reboot_device`
- Data and APN: `check_data_restriction_status`, `toggle_data_saver_mode`, `check_apn_settings`, `set_apn_settings`, `reset_apn_settings`
- Wi-Fi, calling, VPN: `check_wifi_status`, `toggle_wifi`, `check_wifi_calling_status`, `toggle_wifi_calling`, `check_vpn_status`, `connect_vpn`, `disconnect_vpn`
- Apps and MMS: `check_installed_apps`, `check_app_status`, `check_app_permissions`, `grant_app_permission`, `can_send_mms`
- Payment on the device: `check_payment_request`, `make_payment`

Source of the names: `tau2.domains.telecom.tools.TelecomTools` and `user_tools.TelecomUserTools`, methods marked `@is_tool`. The code reader is `rsi_harness.adapters.tau2.tool_catalog.telecom_tool_surfaces`.

Other telecom facts worth asking about later:

- One tool call per turn, and not in the same turn as a user message (domain policy).
- Transfer only through `transfer_to_human_agents`, then the hold message.
- Policy files live under `tau2-bench/data/tau2/domains/telecom/` (`main_policy.md`, `tech_support_manual.md`). They are protected. The harness does not rewrite them.
- Official `test` is the upstream `base` split (114 tasks). `opt` / `val` / `select` come from the rest. Pin is commit `96a3ef9`.

## What a full dev run is

`configs/tau2-dev.yaml` runs the improvement loop on `opt` and `val` only. It does not score `select`. That file is the command to use for the full telecom loop. It is not a license to publish a test number.
