using System;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

// Project 9: moves a character forward from calf-EMG UDP messages sent by bioradio_unity_bridge_v2.py
// (or replay_csv_to_unity.py). Attach to a Capsule/character. Two control modes:
//   Speed : forward speed follows the normalised envelope (env_norm, 0-1)
//   Step  : every detected calf burst (step_event) gives one stride impulse; cadence sets speed
// Safety: if no packet arrives for timeoutSeconds the character stops.
public class EmgWalkingController : MonoBehaviour
{
    public enum ControlMode { Speed, Step }
    public int udpPort = 50557;
    public ControlMode mode = ControlMode.Step;
    public float maxSpeed = 1.6f;        // m/s at env_norm = 1 (Speed mode)
    public float strideLength = 1.4f;    // metres per detected calf burst = one stride of the dominant leg, i.e. two steps (Step mode)
    public float acceleration = 4f;      // smoothing of speed changes
    public float timeoutSeconds = 0.5f;  // stop if bridge goes silent
    public bool useActiveFlag = true;    // Speed mode: only move while 'active'
    public Animator animator;            // optional, float parameter "Speed"
    public bool logToCsv = true;
    [Header("Direct clip playback (no Animator Controller needed)")]
    public AnimationClip idleClip;       // drag the clip inside Idle.fbx
    public AnimationClip walkClip;       // drag the clip inside Walk.fbx (made 'In Place' on Mixamo)
    public float walkRefSpeed = 1.4f;    // m/s at which the walk clip plays at normal speed

    PlayableGraph graph; AnimationMixerPlayable mixer; AnimationClipPlayable idleP, walkP; bool useClips; float idleT, walkT;

    UdpClient receiver; Thread thread; volatile bool listening;
    readonly object gate = new object();
    float envNorm; bool active; int steps; int stepsHandled; double lastPacketTime; string filterMode = "-"; float envMv;
    bool wasFresh; float speed, targetSpeed, stepImpulse; float distance; float startTime = -1f; StreamWriter log; float lastLog;
    Vector3 startPos; int hits; float frozenUntil, flashUntil;

    [Serializable] class Msg { public int channel; public float raw_mv; public float rms_mv; public float env_norm; public int active; public int steps; public int step_event; public string mode; }

    void Start()
    {
        startPos = transform.position;
        if (animator == null) animator = GetComponentInChildren<Animator>();   // auto-find the character's Animator
        if (animator != null) animator.applyRootMotion = false;
        if (animator == null) Debug.LogWarning("EmgWalkingController: no Animator found on the character (drag the character under 'player').");
        else if (animator.avatar == null) Debug.LogWarning("EmgWalkingController: the Animator has no Avatar - set Rig > Animation Type = Humanoid on the character FBX and press Apply.");
        if (animator != null && walkClip != null)
        {
            if (idleClip == null) idleClip = walkClip;
            animator.runtimeAnimatorController = null;
            graph = PlayableGraph.Create("EmgWalk"); graph.SetTimeUpdateMode(DirectorUpdateMode.GameTime);
            var output = AnimationPlayableOutput.Create(graph, "Anim", animator);
            mixer = AnimationMixerPlayable.Create(graph, 2);
            idleP = AnimationClipPlayable.Create(graph, idleClip); walkP = AnimationClipPlayable.Create(graph, walkClip);
            idleP.SetSpeed(0); walkP.SetSpeed(0);
            graph.Connect(idleP, 0, mixer, 0); graph.Connect(walkP, 0, mixer, 1);
            mixer.SetInputWeight(0, 1f); mixer.SetInputWeight(1, 0f);
            output.SetSourcePlayable(mixer); graph.Play(); useClips = true;
            Debug.Log("EmgWalkingController: playing idle/walk clips directly.");
        }
        else Debug.Log("EmgWalkingController: animator=" + (animator ? animator.name : "none") + " controller=" + (animator && animator.runtimeAnimatorController ? animator.runtimeAnimatorController.name : "none") + " (assign Idle Clip and Walk Clip for direct playback)");
        try
        {
            receiver = new UdpClient(new IPEndPoint(IPAddress.Loopback, udpPort));
            receiver.Client.ReceiveTimeout = 500; listening = true;
            thread = new Thread(Loop) { IsBackground = true }; thread.Start();
        }
        catch (Exception e) { Debug.LogError("UDP startup: " + e.Message); }
        if (logToCsv)
        {
            string p = Path.Combine(Application.persistentDataPath, "walk_log_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".csv");
            log = new StreamWriter(p); log.WriteLine("t_s,filter,control,env_mv,env_norm,active,steps,speed_mps,distance_m,hits"); Debug.Log("Logging to " + p);
        }
    }

    void Loop()
    {
        var ep = new IPEndPoint(IPAddress.Loopback, 0);
        while (listening)
        {
            try
            {
                var m = JsonUtility.FromJson<Msg>(Encoding.UTF8.GetString(receiver.Receive(ref ep)));
                if (m == null) continue;
                lock (gate) { envNorm = m.env_norm; envMv = m.rms_mv; active = m.active != 0; steps = m.steps; filterMode = m.mode; lastPacketTime = AppTime(); }
            }
            catch (SocketException) { }
            catch (ObjectDisposedException) { break; }
            catch (Exception) { }
        }
    }
    static double AppTime() { return (DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalSeconds; }

    void Update()
    {
        float n; bool act; int st; bool fresh; float mv; string fm;
        lock (gate) { n = envNorm; act = active; st = steps; mv = envMv; fm = filterMode; fresh = (AppTime() - lastPacketTime) < timeoutSeconds && lastPacketTime > 0; }
        if (fresh && !wasFresh) stepsHandled = st;   // ignore steps counted before Unity connected
        wasFresh = fresh;
        if (!fresh) { n = 0; act = false; stepImpulse = 0; stepsHandled = st; }   // timeout => stop
        else if (startTime < 0 && (act || st > 0)) startTime = Time.time;
        if (mode == ControlMode.Speed) targetSpeed = (act || !useActiveFlag) ? n * maxSpeed : 0f;
        else
        {
            int newSteps = st - stepsHandled; if (newSteps < 0) newSteps = 0; stepsHandled = st;
            stepImpulse += newSteps * strideLength;                 // metres still to cover
            float dist = Mathf.Min(stepImpulse, maxSpeed * Time.deltaTime * 2f);
            targetSpeed = Time.deltaTime > 0 ? dist / Time.deltaTime : 0f; stepImpulse -= dist;
        }
        if (Time.time < frozenUntil) { targetSpeed = 0f; speed = 0f; stepImpulse = 0f; stepsHandled = st; }   // brief pause after a hit
        speed = Mathf.MoveTowards(speed, targetSpeed, acceleration * Time.deltaTime);
        float step = speed * Time.deltaTime; transform.Translate(Vector3.forward * step, Space.World); distance += step;
        if (useClips)
        {
            float w = Mathf.Clamp01(speed / walkRefSpeed);
            mixer.SetInputWeight(0, 1f - w); mixer.SetInputWeight(1, w);
            idleT += Time.deltaTime; walkT += Time.deltaTime * Mathf.Max(0.4f, speed / walkRefSpeed);
            idleP.SetTime(idleT % Mathf.Max(0.01f, idleClip.length)); walkP.SetTime(walkT % Mathf.Max(0.01f, walkClip.length));
        }
        else if (animator != null) animator.SetFloat("Speed", speed, 0.08f, Time.deltaTime);
        if (log != null && Time.time - lastLog > 0.1f)
        {
            lastLog = Time.time;
            log.WriteLine(string.Format(CultureInfo.InvariantCulture, "{0:F2},{1},{2},{3:F5},{4:F3},{5},{6},{7:F3},{8:F3},{9}", Time.time, fm, mode, mv, n, act ? 1 : 0, st, speed, distance, hits));
        }
        hud = string.Format(CultureInfo.InvariantCulture, "filter {0} | {1} | env {2:F4} mV norm {3:F2} | {4} | steps {5} | speed {6:F2} m/s | dist {7:F1} m{8}", fm, mode, mv, n, act ? "ACTIVE" : "rest", st, speed, distance, fresh ? "" : " | NO SIGNAL");
    }
    string hud = "";
    void OnGUI()
    {
        GUI.Label(new Rect(10, 10, 1000, 25), hud);
        if (GUI.Button(new Rect(10, 40, 160, 28), "Toggle Speed/Step")) mode = mode == ControlMode.Speed ? ControlMode.Step : ControlMode.Speed;
        GUI.Label(new Rect(10, 118, 300, 25), "Hammer hits: " + hits);
        if (Time.time < flashUntil)
        {
            GUI.color = new Color(1f, 0f, 0f, 0.45f * (flashUntil - Time.time) / 0.8f); GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture); GUI.color = Color.white;
            var st = new GUIStyle(GUI.skin.label) { fontSize = 30, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter }; st.normal.textColor = Color.white;
            GUI.Label(new Rect(Screen.width / 2 - 250, Screen.height / 2 - 30, 500, 60), "OUCH! Back to the start", st);
        }
    }
    public int Hits { get { return hits; } }
    // Called by SwingingHammer when its head touches the player: back to the start, short pause.
    public void Hit()
    {
        if (Time.time < frozenUntil) return;
        hits++; frozenUntil = Time.time + 1.2f; flashUntil = Time.time + 0.8f;
        transform.position = startPos; distance = 0f; speed = 0f; stepImpulse = 0f;
    }
    public float Distance { get { return distance; } }
    public float ElapsedSinceStart { get { return startTime < 0 ? 0f : Time.time - startTime; } }

    void OnDestroy()
    {
        if (graph.IsValid()) graph.Destroy();
        listening = false; if (receiver != null) receiver.Close(); if (thread != null && thread.IsAlive) thread.Join(1000);
        if (log != null) { log.Flush(); log.Close(); }
    }
}
