using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

// Project 9 - optional testing aid, for running the game without the BioRadio.
// Press SPACE (or click the button) to simulate one detected calf burst = one stride.
// It sends the same UDP messages as bioradio_unity_bridge_v2.py to EmgWalkingController, so the game code is unchanged.
// It stays silent until the first press, so it never interferes with the real bridge or the replay tool.
public class KeyboardStepSimulator : MonoBehaviour
{
    public int udpPort = 50557;
    public KeyCode stepKey = KeyCode.Space;

    UdpClient sender; IPEndPoint target;
    bool simulating; int steps; float lastSend, lastStep = -10f, pendingStepAt = -1f;

    void Start() { sender = new UdpClient(); target = new IPEndPoint(IPAddress.Loopback, udpPort); }

    void OnGUI()
    {
        var e = Event.current;
        if (e != null && e.type == EventType.KeyDown && e.keyCode == stepKey) { Press(); e.Use(); }
        string label = simulating ? "Keyboard test: SPACE = 1 stride" : "Start keyboard test (SPACE)";
        if (GUI.Button(new Rect(180, 40, 240, 28), label)) Press();
    }

    void Press()
    {
        if (Time.unscaledTime - lastStep < 0.2f) return;          // ignore key auto-repeat
        if (!simulating)
        {
            // first press: connect with steps = 0, then give the first stride a moment later
            simulating = true; steps = 0; Send(); pendingStepAt = Time.unscaledTime + 0.15f; lastStep = Time.unscaledTime;
            return;
        }
        Step();
    }

    void Step() { steps++; lastStep = Time.unscaledTime; Send(); }

    void Update()
    {
        if (!simulating) return;
        if (pendingStepAt > 0f && Time.unscaledTime >= pendingStepAt) { pendingStepAt = -1f; Step(); }
        if (Time.unscaledTime - lastSend >= 0.05f) Send();          // heartbeat, like the bridge (every 50 ms)
    }

    void Send()
    {
        if (sender == null) return;
        lastSend = Time.unscaledTime;
        bool active = Time.unscaledTime - lastStep < 0.35f;
        string json = string.Format(CultureInfo.InvariantCulture,
            "{{\"channel\":1,\"raw_mv\":0,\"rms_mv\":0,\"env_norm\":{0},\"active\":{1},\"steps\":{2},\"step_event\":{3},\"mode\":\"KEY\"}}",
            active ? "1.0" : "0.0", active ? 1 : 0, steps, active ? 1 : 0);
        byte[] b = Encoding.UTF8.GetBytes(json);
        try { sender.Send(b, b.Length, target); } catch (SocketException) { }
    }

    void OnDestroy() { if (sender != null) sender.Close(); }
}
