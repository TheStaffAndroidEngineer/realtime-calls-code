"""Huddle: call-control and simulated transport callbacks, no captured media."""

import uuid
from base import BaseService, Problem, fields, integer, text, run


class Service(BaseService):
    KIND = "huddle"

    def seed(self):
        return {"room": None, "incarnation": 0}

    def view(self, state, now):
        return state

    def apply(self, state, action, args, now):
        if action == "start":
            fields(args, set())
            if state["room"] and state["room"]["phase"] != "ENDED":
                return {"accepted": False, "reason": "A call already exists"}
            state["incarnation"] += 1
            state["room"] = {
                "id": str(uuid.uuid4()),
                "incarnation": state["incarnation"],
                "generation": 1,
                "phase": "RINGING",
                "transport": "IDLE",
                "muted": False,
                "peer": "Mira",
                "startedAt": now,
            }
            return {"accepted": True}
        room = state["room"]
        if action in {"accept", "reconnect", "end", "mute", "ready", "disconnect"}:
            names = {"roomId", "incarnation", "generation"} | (
                {"muted"} if action == "mute" else set()
            )
            fields(args, names)
            text(args["roomId"], 40)
            integer(args["incarnation"], 1)
            integer(args["generation"], 1)
            if not room or any(
                args[a] != room[b]
                for a, b in [
                    ("roomId", "id"),
                    ("incarnation", "incarnation"),
                    ("generation", "generation"),
                ]
            ):
                return {
                    "accepted": False,
                    "reason": "Callback or intent belongs to an old call connection",
                }
            if room["phase"] == "ENDED":
                return {"accepted": False, "reason": "This call has ended"}
            if action == "end":
                room["phase"] = "ENDED"
                room["transport"] = "CLOSED"
            elif action == "accept":
                if room["phase"] != "RINGING":
                    return {"accepted": False, "reason": "Call is no longer ringing"}
                room["phase"] = "JOINED"
                room["transport"] = "CONNECTING"
            elif action == "mute":
                if type(args["muted"]) is not bool:
                    raise Problem("muted must be boolean")
                room["muted"] = args["muted"]
            else:
                if room["phase"] != "JOINED":
                    return {"accepted": False, "reason": "Peer has not joined"}
                if action == "reconnect":
                    room["generation"] += 1
                    room["transport"] = "CONNECTING"
                elif action == "ready":
                    room["transport"] = "CONNECTED"
                elif action == "disconnect":
                    room["transport"] = "RECONNECTING"
            return {"accepted": True}
        raise Problem("Unknown action")


if __name__ == "__main__":
    run(Service, 8918)
