package staff.android.huddle
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import java.util.UUID
const val ABOUT="Huddle is a two-person call-control simulator. It does not capture a microphone or camera, carry media, or execute WebRTC/ICE/TURN. Simulated callbacks expose old connection and ended-call races."
fun validateView(data:JSONObject){
    require(data.get("incarnation") is Int && data.getInt("incarnation") >= 0)
    require(data.has("room"))
    if (data.isNull("room")) return
    val r = data.getJSONObject("room")
    UUID.fromString(r.getString("id"))
    require(r.get("incarnation") is Int && r.getInt("incarnation") == data.getInt("incarnation"))
    require(r.get("generation") is Int && r.getInt("generation") > 0)
    require(r.getString("phase") in setOf("RINGING", "JOINED", "ENDED"))
    require(
        r.getString("transport") in
            setOf("IDLE", "CONNECTING", "CONNECTED", "RECONNECTING", "CLOSED"))
    require(r.get("muted") is Boolean && r.getString("peer").isNotBlank())
}
fun grant(r:JSONObject)=JSONObject().put("roomId",r.getString("id")).put("incarnation",r.getInt("incarnation")).put("generation",r.getInt("generation"))
@Composable fun Product(state: CaseState, model: CaseModel, elapsed: Long) {
    val room = state.data?.optJSONObject("room")
    val phase = room?.getString("phase")
    val status = when {
        state.data == null -> if (state.busy) "Loading call room" else "Call room unavailable"
        room == null -> "Ready when you are"
        phase == "ENDED" -> "Call ended"
        phase == "RINGING" -> "Waiting for Mira"
        room.getString("transport") == "CONNECTED" -> "Simulated media connected"
        room.getString("transport") == "RECONNECTING" -> "Connection interrupted"
        else -> "Mira joined · media connecting"
    }
    Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = RoundedCornerShape(28.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(horizontal = 24.dp, vertical = 28.dp).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("DESIGN CATCH-UP", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSecondaryContainer)
            Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primary) {
                Box(Modifier.size(112.dp), contentAlignment = Alignment.Center) { Text("M", fontFamily = HeadingFont, fontSize = 48.sp, color = MaterialTheme.colorScheme.onPrimary) }
            }
            Text(room?.optString("peer") ?: "Mira", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSecondaryContainer)
            Text(status, style = MaterialTheme.typography.titleMedium, modifier = Modifier.testTag("call-status"), color = MaterialTheme.colorScheme.onSecondaryContainer)
            if (phase == "RINGING") Text("Open Lab to let the simulated participant join.", color = MaterialTheme.colorScheme.onSecondaryContainer)
        }
    }
    Text("Simulated call · no audio or video is captured or transmitted", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    if (room != null && phase == "JOINED") {
        Text(if (room.getBoolean("muted")) "Simulated microphone: muted" else "Simulated microphone: on", style = MaterialTheme.typography.titleMedium)
        OutlinedButton(onClick = { model.send("reconnect", grant(room)) }, enabled = ready(state), modifier = Modifier.fillMaxWidth().testTag("reconnect")) { Text("Try a new connection") }
    }
}

@Composable fun HuddleActions(state: CaseState, model: CaseModel) {
    val room = state.data?.optJSONObject("room")
    if (room == null || room.getString("phase") == "ENDED") {
        Button(onClick = { model.send("start") }, enabled = ready(state) && state.data != null, modifier = Modifier.fillMaxWidth().testTag("start")) { Text("Start simulated call") }
    } else FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (room.getString("phase") == "JOINED") OutlinedButton(onClick = { model.send("mute", grant(room).put("muted", !room.getBoolean("muted"))) }, enabled = ready(state), modifier = Modifier.testTag("mute")) { Text(if (room.getBoolean("muted")) "Unmute" else "Mute") }
        Button(onClick = { model.send("end", grant(room)) }, enabled = ready(state), colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error, contentColor = MaterialTheme.colorScheme.onError), modifier = Modifier.testTag("end")) { Text("End call") }
    }
}

@Composable fun HuddleLab(state: CaseState, model: CaseModel) {
    val room = state.data?.optJSONObject("room")
    if (room == null) Text("Start a simulated call from the call screen first.")
    else {
        Text("Room ${room.getString("id")}\nIncarnation ${room.getInt("incarnation")} · connection generation ${room.getInt("generation")}\nPhase ${room.getString("phase")} · transport ${room.getString("transport")}", style = MaterialTheme.typography.bodySmall)
        if (room.getString("phase") == "RINGING") Button(onClick = { model.send("accept", grant(room)) }, enabled = ready(state), modifier = Modifier.testTag("accept")) { Text("Mira joins simulation") }
        Text("Use the companion tools for ready callbacks, stale-generation races and dropped replies. Ended calls remain ended even when old callbacks arrive.")
    }
}
