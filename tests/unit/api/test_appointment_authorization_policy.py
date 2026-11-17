from api.policies.appointment_authorization_policy import (
    AppointmentAuthorizationPolicy,
)


def test_agent_can_read_all_and_write_appointments():
    assert AppointmentAuthorizationPolicy.can_read_all("agent")
    assert AppointmentAuthorizationPolicy.can_write("agent")
    assert not AppointmentAuthorizationPolicy.can_read_own("agent")


def test_existing_appointment_permissions_remain_restricted():
    assert AppointmentAuthorizationPolicy.can_read_all("admin")
    assert AppointmentAuthorizationPolicy.can_read_all("manager")
    assert AppointmentAuthorizationPolicy.can_read_all("policy_approver")
    assert AppointmentAuthorizationPolicy.can_write("admin")
    assert AppointmentAuthorizationPolicy.can_write("manager")
    assert not AppointmentAuthorizationPolicy.can_write("policy_approver")
    assert not AppointmentAuthorizationPolicy.can_read_all("patient")
