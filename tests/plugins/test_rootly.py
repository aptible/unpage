from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from unpage.knowledge import Graph
from unpage.plugins.rootly.client import RootlyClient
from unpage.plugins.rootly.plugin import RootlyPlugin

if TYPE_CHECKING:
    from fastmcp import Client


@pytest.fixture
def mock_rootly_client():
    """Mock RootlyClient for testing."""
    client = AsyncMock(spec=RootlyClient)
    return client


@pytest.fixture
def rootly_plugin(mock_rootly_client):
    """Create a RootlyPlugin instance with mocked client."""
    plugin = RootlyPlugin(api_key="test-key")
    plugin._client = mock_rootly_client
    return plugin


@pytest.mark.asyncio
async def test_get_incident_details(rootly_plugin, mock_rootly_client):
    """Test getting incident details."""
    incident_id = "test-incident-123"
    expected_response = {
        "data": {
            "id": incident_id,
            "type": "incidents",
            "attributes": {
                "title": "Test Incident",
                "status": "investigating"
            }
        }
    }

    mock_rootly_client.get_incident.return_value = expected_response

    result = await rootly_plugin.get_incident_details(incident_id)

    assert result == expected_response
    mock_rootly_client.get_incident.assert_called_once_with(incident_id)


@pytest.mark.asyncio
async def test_get_alert_details_for_incident(rootly_plugin, mock_rootly_client):
    """Test getting alert details for an incident."""
    incident_id = "test-incident-123"
    expected_response = {
        "data": [
            {
                "id": "event-1",
                "type": "incident_events",
                "attributes": {
                    "kind": "alert",
                    "description": "Test alert"
                }
            }
        ]
    }

    mock_rootly_client.get_incident_events.return_value = expected_response

    result = await rootly_plugin.get_alert_details_for_incident(incident_id)

    assert result == expected_response["data"]
    mock_rootly_client.get_incident_events.assert_called_once_with(incident_id)


@pytest.mark.asyncio
async def test_post_status_update(rootly_plugin, mock_rootly_client):
    """Test posting a status update with default external visibility."""
    incident_id = "test-incident-123"
    message = "Investigation is ongoing"

    # Mock the create_incident_event_new call that post_status_update now uses
    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {
            "id": "test-event-123",
            "type": "incident_events",
            "attributes": {"event": f"Status Update: {message}"}
        }
    }

    await rootly_plugin.post_status_update(incident_id, message)

    # Should call create_incident_event_new with status update and external visibility
    mock_rootly_client.create_incident_event_new.assert_called_once()
    call_args = mock_rootly_client.create_incident_event_new.call_args
    assert call_args[0][0] == incident_id
    event_data = call_args[0][1]
    assert f"Status Update: {message}" in event_data["data"]["attributes"]["event"]
    assert event_data["data"]["attributes"]["visibility"] == "external"


@pytest.mark.asyncio
async def test_post_status_update_custom_visibility(rootly_plugin, mock_rootly_client):
    """Test posting a status update with custom visibility."""
    incident_id = "test-incident-123"
    message = "Internal investigation notes"
    visibility = "internal"

    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {"id": "test-event-123", "type": "incident_events"}
    }

    await rootly_plugin.post_status_update(incident_id, message, visibility)

    call_args = mock_rootly_client.create_incident_event_new.call_args
    event_data = call_args[0][1]
    assert event_data["data"]["attributes"]["visibility"] == "internal"


@pytest.mark.asyncio
async def test_resolve_incident(rootly_plugin, mock_rootly_client):
    """Test resolving an incident."""
    incident_id = "test-incident-123"
    resolution_message = "Issue has been resolved"

    await rootly_plugin.resolve_incident(incident_id, resolution_message)

    # Should call update_incident with resolved status and resolution message
    mock_rootly_client.update_incident.assert_called_once()
    call_args = mock_rootly_client.update_incident.call_args
    assert call_args[0][0] == incident_id
    update_data = call_args[0][1]
    assert update_data["data"]["attributes"]["status"] == "resolved"
    assert update_data["data"]["attributes"]["resolution_message"] == resolution_message


@pytest.mark.asyncio
async def test_resolve_incident_without_message(rootly_plugin, mock_rootly_client):
    """Test resolving an incident without a resolution message."""
    incident_id = "test-incident-123"

    await rootly_plugin.resolve_incident(incident_id)

    # Should call update_incident with resolved status only
    mock_rootly_client.update_incident.assert_called_once()
    call_args = mock_rootly_client.update_incident.call_args
    assert call_args[0][0] == incident_id
    update_data = call_args[0][1]
    assert update_data["data"]["attributes"]["status"] == "resolved"
    # Should not have resolution_message when none provided
    assert "resolution_message" not in update_data["data"]["attributes"]


@pytest.mark.asyncio
async def test_mitigate_incident(rootly_plugin, mock_rootly_client):
    """Test mitigating an incident."""
    incident_id = "test-incident-123"

    await rootly_plugin.mitigate_incident(incident_id)

    # Should call update_incident with mitigated status
    mock_rootly_client.update_incident.assert_called_once()
    call_args = mock_rootly_client.update_incident.call_args
    assert call_args[0][0] == incident_id
    update_data = call_args[0][1]
    assert update_data["data"]["attributes"]["status"] == "mitigated"


@pytest.mark.asyncio
async def test_acknowledge_incident(rootly_plugin, mock_rootly_client):
    """Test acknowledging an incident."""
    incident_id = "test-incident-123"

    await rootly_plugin.acknowledge_incident(incident_id)

    # Should call update_incident with in_triage status (Rootly's acknowledgment)
    mock_rootly_client.update_incident.assert_called_once()
    call_args = mock_rootly_client.update_incident.call_args
    assert call_args[0][0] == incident_id
    update_data = call_args[0][1]
    assert update_data["data"]["attributes"]["status"] == "in_triage"


@pytest.mark.asyncio
async def test_populate_graph(rootly_plugin, mock_rootly_client):
    """Test populating the knowledge graph with incidents."""
    graph = Graph()

    # Mock incident data
    incident_data = {
        "id": "incident-123",
        "type": "incidents",
        "attributes": {
            "title": "Test Incident",
            "status": "investigating"
        }
    }

    mock_rootly_client.list_incidents.return_value = {
        "data": [incident_data]
    }

    await rootly_plugin.populate_graph(graph)

    # Check that the incident was added to the graph
    nodes = []
    async for node in graph.iter_nodes():
        nodes.append(node)

    assert len(nodes) == 1
    node = nodes[0]
    assert node.node_id == "rootly_incident:incident-123"
    assert node.incident_id == "incident-123"
    assert node.title == "Test Incident"
    assert node.status == "investigating"


@pytest.mark.asyncio
async def test_add_incident_event(rootly_plugin, mock_rootly_client):
    """Test adding a general incident event."""
    incident_id = "test-incident-123"
    event_description = "Database connection pool exhausted"

    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {
            "id": "test-event-123",
            "type": "incident_events",
            "attributes": {"event": event_description}
        }
    }

    result = await rootly_plugin.add_incident_event(incident_id, event_description)

    # Should call create_incident_event_new with proper structure
    mock_rootly_client.create_incident_event_new.assert_called_once()
    call_args = mock_rootly_client.create_incident_event_new.call_args
    assert call_args[0][0] == incident_id

    event_data = call_args[0][1]
    assert event_data["data"]["type"] == "incident_events"
    assert event_data["data"]["attributes"]["event"] == event_description
    assert event_data["data"]["attributes"]["kind"] == "event"
    assert event_data["data"]["attributes"]["source"] == "api"
    assert event_data["data"]["attributes"]["visibility"] == "internal"

    assert result["data"]["id"] == "test-event-123"


@pytest.mark.asyncio
async def test_log_investigation_finding(rootly_plugin, mock_rootly_client):
    """Test logging an investigation finding with default internal visibility."""
    incident_id = "test-incident-123"
    finding = "High CPU utilization on web servers"
    source = "metrics"

    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {"id": "test-event-123", "type": "incident_events"}
    }

    result = await rootly_plugin.log_investigation_finding(incident_id, finding, source)

    # Should create event with investigation finding format and internal visibility
    mock_rootly_client.create_incident_event_new.assert_called_once()
    call_args = mock_rootly_client.create_incident_event_new.call_args
    event_data = call_args[0][1]
    expected_description = f"Investigation Finding: {finding} (Source: {source})"
    assert event_data["data"]["attributes"]["event"] == expected_description
    assert event_data["data"]["attributes"]["visibility"] == "internal"


@pytest.mark.asyncio
async def test_log_investigation_finding_custom_visibility(rootly_plugin, mock_rootly_client):
    """Test logging an investigation finding with custom visibility."""
    incident_id = "test-incident-123"
    finding = "Customer-facing issue confirmed"
    visibility = "external"

    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {"id": "test-event-123", "type": "incident_events"}
    }

    await rootly_plugin.log_investigation_finding(incident_id, finding, visibility=visibility)

    call_args = mock_rootly_client.create_incident_event_new.call_args
    event_data = call_args[0][1]
    assert event_data["data"]["attributes"]["visibility"] == "external"


@pytest.mark.asyncio
async def test_log_action_taken(rootly_plugin, mock_rootly_client):
    """Test logging an action taken with default internal visibility."""
    incident_id = "test-incident-123"
    action = "Scaled web servers from 3 to 6"
    outcome = "CPU utilization decreased to normal"

    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {"id": "test-event-123", "type": "incident_events"}
    }

    result = await rootly_plugin.log_action_taken(incident_id, action, outcome)

    mock_rootly_client.create_incident_event_new.assert_called_once()
    call_args = mock_rootly_client.create_incident_event_new.call_args
    event_data = call_args[0][1]
    expected_description = f"Action Taken: {action} → Result: {outcome}"
    assert event_data["data"]["attributes"]["event"] == expected_description
    assert event_data["data"]["attributes"]["visibility"] == "internal"


@pytest.mark.asyncio
async def test_log_action_taken_custom_visibility(rootly_plugin, mock_rootly_client):
    """Test logging an action taken with custom visibility."""
    incident_id = "test-incident-123"
    action = "Updated status page"
    visibility = "external"

    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {"id": "test-event-123", "type": "incident_events"}
    }

    await rootly_plugin.log_action_taken(incident_id, action, visibility=visibility)

    call_args = mock_rootly_client.create_incident_event_new.call_args
    event_data = call_args[0][1]
    assert event_data["data"]["attributes"]["visibility"] == "external"


@pytest.mark.asyncio
async def test_log_escalation(rootly_plugin, mock_rootly_client):
    """Test logging an escalation with default internal visibility."""
    incident_id = "test-incident-123"
    escalated_to = "Senior DevOps Team"
    reason = "Need infrastructure expertise"

    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {"id": "test-event-123", "type": "incident_events"}
    }

    result = await rootly_plugin.log_escalation(incident_id, escalated_to, reason)

    mock_rootly_client.create_incident_event_new.assert_called_once()
    call_args = mock_rootly_client.create_incident_event_new.call_args
    event_data = call_args[0][1]
    expected_description = f"Escalated to {escalated_to} - Reason: {reason}"
    assert event_data["data"]["attributes"]["event"] == expected_description
    assert event_data["data"]["attributes"]["visibility"] == "internal"


@pytest.mark.asyncio
async def test_log_escalation_custom_visibility(rootly_plugin, mock_rootly_client):
    """Test logging an escalation with custom visibility."""
    incident_id = "test-incident-123"
    escalated_to = "External Support Team"
    visibility = "external"

    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {"id": "test-event-123", "type": "incident_events"}
    }

    await rootly_plugin.log_escalation(incident_id, escalated_to, visibility=visibility)

    call_args = mock_rootly_client.create_incident_event_new.call_args
    event_data = call_args[0][1]
    assert event_data["data"]["attributes"]["visibility"] == "external"


@pytest.mark.asyncio
async def test_log_communication(rootly_plugin, mock_rootly_client):
    """Test logging a communication event."""
    incident_id = "test-incident-123"
    communication_type = "Customer Notification"
    details = "Sent status page update about performance issues"
    visibility = "external"

    mock_rootly_client.create_incident_event_new.return_value = {
        "data": {"id": "test-event-123", "type": "incident_events"}
    }

    result = await rootly_plugin.log_communication(incident_id, communication_type, details, visibility)

    mock_rootly_client.create_incident_event_new.assert_called_once()
    call_args = mock_rootly_client.create_incident_event_new.call_args
    event_data = call_args[0][1]
    expected_description = f"{communication_type}: {details}"
    assert event_data["data"]["attributes"]["event"] == expected_description
    assert event_data["data"]["attributes"]["visibility"] == visibility


@pytest.mark.asyncio
async def test_get_incident_timeline(rootly_plugin, mock_rootly_client):
    """Test getting incident timeline."""
    incident_id = "test-incident-123"
    mock_events = [
        {"id": "event-1", "attributes": {"event": "Incident started", "occurred_at": "2023-01-01T12:00:00Z"}},
        {"id": "event-2", "attributes": {"event": "Investigation began", "occurred_at": "2023-01-01T12:05:00Z"}}
    ]

    mock_rootly_client.get_incident_events.return_value = {"data": mock_events}

    result = await rootly_plugin.get_incident_timeline(incident_id)

    mock_rootly_client.get_incident_events.assert_called_once_with(incident_id)
    assert result == mock_events
    assert len(result) == 2


@pytest.mark.asyncio
async def test_update_incident_event(rootly_plugin, mock_rootly_client):
    """Test updating an incident event."""
    event_id = "test-event-123"
    updated_description = "Updated event description"
    visibility = "external"

    mock_rootly_client.update_incident_event.return_value = {
        "data": {
            "id": event_id,
            "type": "incident_events",
            "attributes": {
                "event": updated_description,
                "visibility": visibility
            }
        }
    }

    result = await rootly_plugin.update_incident_event(event_id, updated_description, visibility)

    mock_rootly_client.update_incident_event.assert_called_once()
    call_args = mock_rootly_client.update_incident_event.call_args
    assert call_args[0][0] == event_id

    update_data = call_args[0][1]
    assert update_data["data"]["type"] == "incident_events"
    assert update_data["data"]["id"] == event_id
    assert update_data["data"]["attributes"]["event"] == updated_description
    assert update_data["data"]["attributes"]["visibility"] == visibility

    assert result["data"]["id"] == event_id


@pytest.mark.asyncio
async def test_update_incident_event_default_visibility(rootly_plugin, mock_rootly_client):
    """Test updating an incident event with default visibility."""
    event_id = "test-event-123"
    updated_description = "Updated event description"

    mock_rootly_client.update_incident_event.return_value = {
        "data": {"id": event_id, "type": "incident_events"}
    }

    await rootly_plugin.update_incident_event(event_id, updated_description)

    call_args = mock_rootly_client.update_incident_event.call_args
    update_data = call_args[0][1]
    # Should default to internal visibility
    assert update_data["data"]["attributes"]["visibility"] == "internal"


@pytest.mark.asyncio
async def test_delete_incident_event(rootly_plugin, mock_rootly_client):
    """Test deleting an incident event."""
    event_id = "test-event-123"

    mock_rootly_client.delete_incident_event.return_value = {
        "data": {
            "id": event_id,
            "type": "incident_events"
        }
    }

    result = await rootly_plugin.delete_incident_event(event_id)

    mock_rootly_client.delete_incident_event.assert_called_once_with(event_id)
    assert result["data"]["id"] == event_id


@pytest.mark.asyncio
async def test_mcp_tools_integration(mcp_client: "Client"):
    """Test Rootly plugin tools through MCP server."""
    # This test would require the Rootly plugin to be enabled in the test config
    # For now, we'll skip it since we don't have a proper test configuration
    pytest.skip("Requires Rootly plugin to be configured in test profile")