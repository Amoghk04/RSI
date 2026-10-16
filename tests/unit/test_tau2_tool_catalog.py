"""Telecom tool catalog separates carrier tools from phone actions."""

from rsi_harness.adapters.tau2.tool_catalog import telecom_tool_surfaces


def test_telecom_surfaces_match_tau2_toolkits() -> None:
    surfaces = telecom_tool_surfaces()
    agent = set(surfaces["agent_tools"])
    user = set(surfaces["user_tools"])
    assert "get_customer_by_phone" in agent
    assert "transfer_to_human_agents" in agent
    assert "toggle_airplane_mode" in user
    assert "run_speed_test" in user
    assert agent.isdisjoint(user)
