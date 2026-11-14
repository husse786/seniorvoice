"""Device API for the portal (PR 10): B4, B5, A16-A18."""

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

ZH = ZoneInfo("Europe/Zurich")
TOKEN = "test-token-123"


@pytest.fixture
def api(env):
    device_api = env.load("device_api")
    server = device_api.make_server("127.0.0.1", 0, device_api.token_hash(TOKEN))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    device_api.grant("sandra", "Sandra Keller", "angehoerige", help_visible=True)
    device_api.grant("mueller", "M. Müller (Spitex)", "spitex")
    device_api.grant("team", "Projektteam", "admin")
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def call(method, path, person="sandra", body=None, token=TOKEN):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(base + path, data=data, method=method)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        if person:
            req.add_header("X-Person-Id", person)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    call.module = device_api
    call.base = base
    call.appointments = __import__("appointments")
    yield call
    server.shutdown()
    server.server_close()


def _future(hours=3):
    return (datetime.now(ZH) + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")


def test_refuses_to_start_open_or_on_all_interfaces(env):
    device_api = env.load("device_api")
    with pytest.raises(ValueError):
        device_api.make_server("127.0.0.1", 0, "")
    for host in ("0.0.0.0", "::", "0", "", "my-pi.local"):
        with pytest.raises(ValueError):
            device_api.make_server(host, 0, device_api.token_hash(TOKEN))


def test_token_and_grant_are_both_required(api):
    assert api("GET", "/v1/status", token=None)[0] == 401
    assert api("GET", "/v1/status", token="wrong")[0] == 401
    assert api("GET", "/v1/status", person=None)[0] == 403
    assert api("GET", "/v1/status", person="stranger")[0] == 403
    status, body = api("GET", "/v1/status")
    assert status == 200 and body["api"] == "1"
    api.module.revoke("sandra")
    assert api("GET", "/v1/appointments")[0] == 403          # revocable


def test_create_list_and_who_entered_it(api):
    status, body = api("POST", "/v1/appointments",
                       body={"title": "Arzt Dr. Meier", "due_local": _future(), "kind": "termin"})
    assert status == 201
    status, body = api("GET", "/v1/appointments", person="mueller")
    item = body["appointments"][0]
    assert item["title"] == "Arzt Dr. Meier" and item["created_by"] == "Sandra Keller"
    assert item["own"] is False and item["reminders"][0]["status"] == "geplant"
    assert api("GET", "/v1/appointments")[1]["appointments"][0]["own"] is True


def test_only_the_author_may_change_or_delete(api):
    _, body = api("POST", "/v1/appointments", body={"title": "Coiffeur", "due_local": _future()})
    appt = body["id"]
    assert api("PUT", f"/v1/appointments/{appt}", person="mueller", body={"title": "x"})[0] == 403
    assert api("DELETE", f"/v1/appointments/{appt}", person="mueller")[0] == 403
    new_time = _future(5)
    assert api("PUT", f"/v1/appointments/{appt}",
               body={"title": "Coiffeur Lea", "due_local": new_time})[0] == 200
    item = api("GET", "/v1/appointments")[1]["appointments"][0]
    assert item["title"] == "Coiffeur Lea" and item["due_local"] == new_time
    assert api("DELETE", f"/v1/appointments/{appt}")[0] == 200
    assert api("GET", "/v1/appointments")[1]["appointments"] == []


def test_seniors_own_appointments_and_callbacks_are_protected(api):
    a = api.appointments
    due = datetime.now(ZH) + timedelta(hours=2)
    own = a.add_appointment("Geburtstag Enkel", due, "Senior")          # no portal account
    a.add_appointment("Rückruf", due, "Gerät", kind="rueckruf")
    items = api("GET", "/v1/appointments")[1]["appointments"]
    assert [i["title"] for i in items] == ["Geburtstag Enkel"]            # callback not shown (B5)
    assert api("DELETE", f"/v1/appointments/{own}")[0] == 403
    assert api("PUT", f"/v1/appointments/{own}", body={"title": "x"})[0] == 403


def test_admin_sees_technology_only(api):
    api("POST", "/v1/appointments", body={"title": "Arzt", "due_local": _future()})
    assert api("GET", "/v1/status", person="team")[0] == 200
    assert api("GET", "/v1/appointments", person="team")[0] == 403
    assert api("GET", "/v1/help", person="team")[0] == 403
    entries = api("GET", "/v1/audit", person="team")[1]["entries"]
    assert {e["person_id"] for e in entries} >= {"sandra"}                # admin: all entries


def test_help_history_only_when_shared(api):
    help_alert = __import__("help_alert")
    help_alert.set_contacts([{"name": "Sandra", "role": "Tochter", "address": "1"}])
    assert api("GET", "/v1/help", person="mueller")[0] == 403
    status, body = api("GET", "/v1/help")
    assert status == 200 and body["alerts"] == []


def test_input_is_checked(api):
    assert api("POST", "/v1/appointments", body={"title": "", "due_local": _future()})[0] == 400
    assert api("POST", "/v1/appointments", body={"title": "x" * 201, "due_local": _future()})[0] == 400
    assert api("POST", "/v1/appointments", body={"title": "A", "due_local": "morgen"})[0] == 400
    assert api("POST", "/v1/appointments", body={"title": "A", "due_local": _future(-2)})[0] == 400
    assert api("POST", "/v1/appointments",
               body={"title": "A", "due_local": _future(), "kind": "rueckruf"})[0] == 400
    assert api("POST", "/v1/appointments",
               body={"title": "A", "due_local": _future(), "pre_minutes": -5})[0] == 400
    assert api("POST", "/v1/appointments", body=["not", "an", "object"])[0] == 400
    assert api("GET", "/v1/unknown")[0] == 404


def test_every_access_is_logged_without_content(api):
    api("POST", "/v1/appointments", body={"title": "Geheimer Arzttermin", "due_local": _future()})
    api("GET", "/v1/appointments", person="stranger")
    api("GET", "/v1/status", token="wrong")
    entries = api.module.list_audit()
    actions = [(e["person_id"], e["action"], e["result"]) for e in entries]
    assert ("sandra", "POST /v1/appointments", 201) in actions
    assert ("stranger", "GET /v1/appointments", 403) in actions
    assert not any(e["result"] == 401 for e in entries)                  # no flooding
    assert "Geheimer" not in json.dumps(entries)
    api("GET", "/v1/appointments", person="mueller")
    own = api("GET", "/v1/audit", person="mueller")[1]["entries"]
    assert own and {e["person_id"] for e in own} == {"mueller"}       # only own entries


def test_access_log_is_purged_after_retention(api):
    now = datetime.now(timezone.utc)
    api.module.audit("sandra", "GET /v1/status", None, 200, now=now - timedelta(days=31))
    api.module.audit("sandra", "GET /v1/status", None, 200, now=now)
    assert api.module.purge_audit() == 1
    assert len(api.module.list_audit("sandra")) == 1


def test_ringing_stops_when_the_appointment_is_deleted(env):
    a = env.load("appointments")

    class Ringer:
        ringing = False

        def ring(self):
            self.ringing = True

        def stop(self):
            self.ringing = False
    ringer = Ringer()
    now = datetime.now(timezone.utc)
    appt = a.add_appointment("Arzt", (now - timedelta(seconds=5)).astimezone(ZH), "Spitex",
                             pre_minutes=0, now=now - timedelta(minutes=1))
    sched = a.ReminderScheduler(ringer, in_call=lambda: False)
    sched.tick()
    assert ringer.ringing
    a.delete_appointment(appt)
    sched.tick()
    assert not ringer.ringing and sched.ringing is None
    assert sched.on_hook_off() is None


def test_update_replans_reminders(env):
    a = env.load("appointments")
    now = datetime.now(timezone.utc)
    appt = a.add_appointment("Arzt", (now + timedelta(hours=3)).astimezone(ZH), "Spitex",
                             created_by_id="x")
    assert len(a.list_appointments()[0]["reminders"]) == 2              # pre + main
    assert a.update_appointment(appt, due_local=(now + timedelta(minutes=10)).astimezone(ZH))
    rems = a.list_appointments()[0]["reminders"]
    assert [r["stage"] for r in rems] == ["main"]                        # pre would be in the past
    assert a.update_appointment(999, title="x") is False


def test_text_change_does_not_ring_again(env):
    a = env.load("appointments")
    now = datetime.now(timezone.utc)
    appt = a.add_appointment("Arzt", (now + timedelta(hours=3)).astimezone(ZH), "Spitex",
                             pre_minutes=0, created_by_id="x")
    conn = a.connect()
    conn.execute("UPDATE reminders SET status = 'bestaetigt', attempts = 1")
    conn.commit()
    conn.close()
    assert a.update_appointment(appt, title="Arzt Dr. Meier")
    rems = a.list_appointments()[0]["reminders"]
    assert [(r["stage"], r["status"]) for r in rems] == [("main", "bestaetigt")]
    # new time keeps the chosen "no pre-reminder"
    assert a.update_appointment(appt, due_local=(now + timedelta(hours=5)).astimezone(ZH))
    assert [r["stage"] for r in a.list_appointments()[0]["reminders"]] == ["main"]


def test_error_closes_connection_and_dates_are_checked(api):
    assert api("POST", "/v1/appointments",
               body={"title": "A", "due_local": "9999-12-31 23:59"})[0] == 400
    assert api("POST", "/v1/appointments",
               body={"title": "A", "due_local": "2027-03-28 02:30"})[0] == 400    # clock change
    import http.client
    port = int(api.base.rsplit(":", 1)[1])
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("PUT", "/v1/appointments/1", body=b'{"title": "x"}',
                 headers={"Authorization": f"Bearer {TOKEN}", "X-Person-Id": "mueller",
                          "Content-Type": "application/json"})
    resp = conn.getresponse()
    assert resp.status == 404 and resp.getheader("Connection") == "close"
    resp.read()
    conn.close()


# --- Rat information (PR 9, B2) ---

def test_advice_entries_over_the_portal(api):
    status, body = api("POST", "/v1/advice", person="mueller",
                       body={"topic": "Telefonnummer Spitex", "text": "044 000 00 00, Mo-Fr 8-17 Uhr."})
    assert status == 201
    item_id = body["id"]
    status, body = api("GET", "/v1/advice")
    entry = body["advice"][0]
    assert entry["topic"] == "Telefonnummer Spitex" and entry["created_by"] == "M. Müller (Spitex)"
    assert entry["own"] is False
    assert api("GET", "/v1/advice", person="mueller")[1]["advice"][0]["own"] is True
    # Only the author may change or delete it (B5)
    assert api("PUT", f"/v1/advice/{item_id}", body={"text": "x"})[0] == 403
    assert api("DELETE", f"/v1/advice/{item_id}")[0] == 403
    assert api("PUT", f"/v1/advice/{item_id}", person="mueller", body={"text": "044 000 00 02."})[0] == 200
    assert api.module.advice.get_item(item_id)["text"] == "044 000 00 02."
    assert api("DELETE", f"/v1/advice/{item_id}", person="mueller")[0] == 200
    assert api("GET", "/v1/advice")[1]["advice"] == []
    assert api("DELETE", f"/v1/advice/{item_id}", person="mueller")[0] == 404


def test_advice_validation_and_admin_has_no_access(api):
    assert api("GET", "/v1/advice", person="team")[0] == 403
    assert api("POST", "/v1/advice", person="team", body={"topic": "a", "text": "b"})[0] == 403
    assert api("POST", "/v1/advice", body={"topic": "", "text": "b"})[0] == 400
    assert api("POST", "/v1/advice", body={"topic": "a", "text": 5})[0] == 400
    assert api("POST", "/v1/advice", body={"topic": "a" * 81, "text": "b"})[0] == 400
    assert api("PUT", "/v1/advice/999", body={"text": "b"})[0] == 404
    _, body = api("POST", "/v1/advice", body={"topic": "Einkauf", "text": "Samstag"})
    assert api("PUT", f"/v1/advice/{body['id']}", body={"text": None})[0] == 400
    assert api("PUT", f"/v1/advice/{body['id']}", body={"text": ""})[0] == 400
    assert api.module.advice.get_item(body["id"])["text"] == "Samstag"
    actions = [e["action"] for e in api.module.list_audit("sandra")]
    assert "POST /v1/advice" in actions and "PUT /v1/advice/{id}" in actions
