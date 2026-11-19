using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

// Builds the walking course AND a scenic outdoor environment at runtime (grass, path, trees, bushes, flowers, hills,
// clouds, sun, fog, lamp posts, START/FINISH gates) plus a follow camera and a progress bar.
// Setup unchanged: empty GameObject 'Course' + this script, drag the player into 'Character'. Press Play.
public class WalkingCourseBuilder : MonoBehaviour
{
    public EmgWalkingController character;
    public float courseLength = 50f;
    public float courseWidth = 4f;
    public Vector3 cameraOffset = new Vector3(0f, 2.2f, -4.5f);
    [Header("Scenery")]
    public bool buildScenery = true;
    public int treeCount = 90;
    public int randomSeed = 7;
    [Header("Swinging hammers")]
    public bool hammers = true;
    public float[] hammerZ = { 18f, 30f, 42f };            // where the hammers hang (metres along the path)
    public float[] hammerPeriod = { 5.6f, 4.8f, 4.4f };    // seconds per swing - smaller = faster = harder
    public float swingAngle = 50f;                          // degrees each side
    [Header("Hammer model (optional) - drag the Electric_hammer FBX here")]
    public GameObject hammerModel;                          // leave empty to use the simple built-in hammer
    public float modelLength = 3.6f;                        // hammer length in metres (the model is scaled to this)
    public float rodLength = 2.2f;                          // steel rod between the beam and the hammer
    public float groundClearance = 0.3f;                    // gap between the hammer head and the ground when hanging straight
    public Color modelTint = new Color(0.20f, 0.42f, 0.90f);

    bool finished; string result = ""; Transform cam, root;
    Material template; readonly Dictionary<Color, Material> mats = new Dictionary<Color, Material>();

    // ---------- helpers ----------
    Material Mat(Color c)
    {
        Material m;
        if (mats.TryGetValue(c, out m)) return m;
        m = new Material(template); m.color = c;
        if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", 0.08f);
        if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", 0f);
        mats[c] = m; return m;
    }
    GameObject Prim(PrimitiveType t, string n, Vector3 pos, Vector3 scale, Color c, Transform parent = null)
    {
        var g = GameObject.CreatePrimitive(t); g.name = n;
        var col = g.GetComponent<Collider>(); if (col != null) Destroy(col);
        g.transform.SetParent(parent != null ? parent : root, false);
        g.transform.position = pos; g.transform.localScale = scale;
        g.GetComponent<Renderer>().sharedMaterial = Mat(c);
        return g;
    }
    void Label(string text, Vector3 pos, float size, Color c)
    {
        var g = new GameObject("Label_" + text); g.transform.SetParent(root, false); g.transform.position = pos;
        var tm = g.AddComponent<TextMesh>(); tm.text = text; tm.characterSize = size; tm.fontSize = 64; tm.anchor = TextAnchor.MiddleCenter; tm.color = c;
        var f = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        if (f != null) { tm.font = f; g.GetComponent<MeshRenderer>().sharedMaterial = f.material; }
    }
    float R(System.Random r, float a, float b) { return a + (float)r.NextDouble() * (b - a); }

    // ---------- build ----------
    void Start()
    {
        var tmp = GameObject.CreatePrimitive(PrimitiveType.Cube); template = tmp.GetComponent<Renderer>().sharedMaterial; Destroy(tmp);
        root = new GameObject("Scenery").transform;
        BuildCourse();
        if (hammers) BuildHammers();
        if (buildScenery) { BuildAtmosphere(); BuildTrees(); BuildHills(); BuildClouds(); BuildGate(0f, "START", new Color(0.85f, 0.2f, 0.2f)); BuildGate(courseLength, "FINISH", new Color(0.15f, 0.7f, 0.3f)); BuildLamps(); }
        if (Camera.main != null) cam = Camera.main.transform;
    }

    void BuildCourse()
    {
        float len = courseLength + 500f;
        Prim(PrimitiveType.Cube, "Grass", new Vector3(0, -0.06f, courseLength * 0.5f + 120f), new Vector3(900f, 0.1f, len), new Color(0.30f, 0.55f, 0.25f));
        Prim(PrimitiveType.Cube, "Path", new Vector3(0, -0.03f, courseLength * 0.5f), new Vector3(courseWidth, 0.1f, courseLength + 30f), new Color(0.74f, 0.66f, 0.52f));
        for (int s = -1; s <= 1; s += 2)
            Prim(PrimitiveType.Cube, "Curb", new Vector3(s * (courseWidth * 0.5f + 0.1f), 0.04f, courseLength * 0.5f), new Vector3(0.2f, 0.16f, courseLength + 30f), new Color(0.85f, 0.85f, 0.85f));
        Prim(PrimitiveType.Cube, "StartLine", new Vector3(0, 0.03f, 0.3f), new Vector3(courseWidth, 0.02f, 0.3f), new Color(0.9f, 0.2f, 0.2f));
        for (int m = 10; m <= (int)courseLength; m += 10)
        {
            bool fin = m == (int)courseLength;
            Prim(PrimitiveType.Cube, "Marker" + m, new Vector3(0, 0.03f, m), new Vector3(courseWidth, 0.02f, fin ? 0.5f : 0.15f), fin ? new Color(0.2f, 0.85f, 0.3f) : Color.white);
            if (!fin) Label(m + " m", new Vector3(courseWidth * 0.5f + 1.3f, 0.9f, m), 0.22f, Color.white);
        }
    }

    void BuildHammers()
    {
        bool useModel = hammerModel != null;
        float pivotY = useModel ? groundClearance + modelLength + rodLength : 7.6f, L = 5.7f, hw = courseWidth * 0.5f + 2.2f;
        Color steel = new Color(.33f, .35f, .38f), dark = new Color(.18f, .18f, .2f), red = new Color(.85f, .15f, .12f);
        for (int i = 0; i < hammerZ.Length; i++)
        {
            float z = hammerZ[i], per = i < hammerPeriod.Length ? hammerPeriod[i] : 2.6f;
            Prim(PrimitiveType.Cylinder, "HammerPostL", new Vector3(-hw, pivotY * 0.5f, z), new Vector3(0.45f, pivotY * 0.5f, 0.45f), dark);
            Prim(PrimitiveType.Cylinder, "HammerPostR", new Vector3(hw, pivotY * 0.5f, z), new Vector3(0.45f, pivotY * 0.5f, 0.45f), dark);
            Prim(PrimitiveType.Cube, "HammerBeam", new Vector3(0, pivotY + 0.1f, z), new Vector3(hw * 2f + 0.5f, 0.45f, 0.6f), dark);
            Prim(PrimitiveType.Cube, "DangerZone", new Vector3(0, 0.035f, z), new Vector3(courseWidth, 0.02f, 1.6f), new Color(1f, .8f, 0f));
            var piv = new GameObject("HammerPivot" + (i + 1)).transform; piv.SetParent(root, false); piv.position = new Vector3(0, pivotY, z);
            Prim(PrimitiveType.Sphere, "PivotBall", new Vector3(0, pivotY, z), Vector3.one * 0.5f, dark, piv);
            Transform headT; float hitR = 0.8f;
            if (useModel)
            {
                Prim(PrimitiveType.Cylinder, "Rod", new Vector3(0, pivotY - rodLength * 0.5f, z), new Vector3(0.12f, rodLength * 0.5f, 0.12f), steel, piv);
                headT = MountModel(piv, out hitR);
            }
            else
            {
                Prim(PrimitiveType.Cylinder, "Rod", new Vector3(0, pivotY - L * 0.5f, z), new Vector3(0.14f, L * 0.5f, 0.14f), steel, piv);
                var head = Prim(PrimitiveType.Cube, "HammerHead", new Vector3(0, pivotY - L, z), new Vector3(1.5f, 1.0f, 1.0f), steel, piv);
                Prim(PrimitiveType.Cube, "HeadBand", new Vector3(0, pivotY - L, z), new Vector3(1.54f, 0.28f, 1.04f), red, piv);
                headT = head.transform;
            }
            var sh = piv.gameObject.AddComponent<SwingingHammer>();
            sh.pivot = piv; sh.head = headT; sh.hitRadius = hitR; sh.player = character; sh.period = per; sh.phase = i * 0.37f; sh.amplitudeDeg = swingAngle;
        }
    }

    // ---- imports the hammer FBX, finds its long axis and heavy end automatically, hangs it head-down, scales and tints it ----
    List<Vector3> Pts(GameObject go)
    {
        var pts = new List<Vector3>(); var verts = new List<Vector3>();
        foreach (var mf in go.GetComponentsInChildren<MeshFilter>())
        {
            if (mf.sharedMesh == null) continue;
            verts.Clear(); mf.sharedMesh.GetVertices(verts); var tr = mf.transform;
            for (int i = 0; i < verts.Count; i++) pts.Add(tr.TransformPoint(verts[i]));
        }
        return pts;
    }
    static void Bnds(List<Vector3> p, out Vector3 mn, out Vector3 mx)
    {
        mn = new Vector3(1e9f, 1e9f, 1e9f); mx = -mn;
        for (int i = 0; i < p.Count; i++) { mn = Vector3.Min(mn, p[i]); mx = Vector3.Max(mx, p[i]); }
    }
    static float Spread(List<Vector3> p, Vector3 axis, float t0, float t1, int a)
    {
        Vector3 mn = new Vector3(1e9f, 1e9f, 1e9f), mx = -mn; bool any = false;
        for (int i = 0; i < p.Count; i++) { float t = Vector3.Dot(p[i], axis); if (t < t0 || t > t1) continue; any = true; mn = Vector3.Min(mn, p[i]); mx = Vector3.Max(mx, p[i]); }
        if (!any) return 0f;
        Vector3 e = mx - mn; return a == 0 ? e.y * e.z : (a == 1 ? e.x * e.z : e.x * e.y);
    }

    Transform MountModel(Transform piv, out float hitR)
    {
        hitR = 0.8f;
        var inst = Instantiate(hammerModel, piv); inst.name = "HammerModel";
        inst.transform.localPosition = Vector3.zero; inst.transform.localRotation = Quaternion.identity; inst.transform.localScale = Vector3.one;
        foreach (var c in inst.GetComponentsInChildren<Collider>()) Destroy(c);
        var pts = Pts(inst);
        if (pts.Count == 0) { Debug.LogWarning("WalkingCourseBuilder: the hammer model has no readable mesh - tick Read/Write on the FBX import settings."); return piv; }
        Vector3 mn, mx; Bnds(pts, out mn, out mx); Vector3 ext = mx - mn;
        int a = (ext.x >= ext.y && ext.x >= ext.z) ? 0 : (ext.y >= ext.z ? 1 : 2);
        Vector3 ea = a == 0 ? Vector3.right : (a == 1 ? Vector3.up : Vector3.forward);
        float tmin = 1e9f, tmax = -1e9f;
        for (int i = 0; i < pts.Count; i++) { float t = Vector3.Dot(pts[i], ea); if (t < tmin) tmin = t; if (t > tmax) tmax = t; }
        float len = tmax - tmin;
        float sLow = Spread(pts, ea, tmin, tmin + 0.25f * len, a), sHigh = Spread(pts, ea, tmax - 0.25f * len, tmax, a);
        Vector3 u1 = ea * (sHigh > sLow ? 1f : -1f);                       // points from the handle end to the heavy head end
        // which perpendicular axis is the head's long side?
        float u1max = -1e9f; for (int i = 0; i < pts.Count; i++) u1max = Mathf.Max(u1max, Vector3.Dot(pts[i], u1));
        Vector3 hmn = new Vector3(1e9f, 1e9f, 1e9f), hmx = -hmn;
        for (int i = 0; i < pts.Count; i++) if (Vector3.Dot(pts[i], u1) >= u1max - 0.3f * len) { hmn = Vector3.Min(hmn, pts[i]); hmx = Vector3.Max(hmx, pts[i]); }
        Vector3 he = hmx - hmn; Vector3 u2 = Vector3.zero; float best = -1f;
        for (int k = 0; k < 3; k++) { if (k == a) continue; float e = k == 0 ? he.x : (k == 1 ? he.y : he.z); if (e > best) { best = e; u2 = k == 0 ? Vector3.right : (k == 1 ? Vector3.up : Vector3.forward); } }
        Quaternion q1 = Quaternion.FromToRotation(u1, Vector3.down);       // head down
        Vector3 u2p = q1 * u2; u2p.y = 0f; if (u2p.sqrMagnitude < 1e-6f) u2p = Vector3.right; u2p.Normalize(); if (Vector3.Dot(u2p, Vector3.right) < 0f) u2p = -u2p;
        inst.transform.localRotation = Quaternion.FromToRotation(u2p, Vector3.right) * q1;   // head's long side along the swing direction
        pts = Pts(inst); Bnds(pts, out mn, out mx);
        inst.transform.localScale = Vector3.one * (modelLength / Mathf.Max(0.01f, mx.y - mn.y));
        pts = Pts(inst); Bnds(pts, out mn, out mx);
        float cx = 0f, cz = 0f; int cnt = 0;
        for (int i = 0; i < pts.Count; i++) if (pts[i].y > mx.y - 0.05f * (mx.y - mn.y)) { cx += pts[i].x; cz += pts[i].z; cnt++; }
        cx /= Mathf.Max(cnt, 1); cz /= Mathf.Max(cnt, 1);
        inst.transform.position += new Vector3(piv.position.x - cx, (piv.position.y - rodLength) - mx.y, piv.position.z - cz);   // handle top hangs from the rod
        // tint (the imported material is not URP) with a blue electric glow
        var m = new Material(template); m.color = modelTint;
        if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", 0.55f); if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", 0.5f);
        m.EnableKeyword("_EMISSION"); if (m.HasProperty("_EmissionColor")) m.SetColor("_EmissionColor", new Color(0.05f, 0.25f, 0.9f) * 1.2f);
        foreach (var r in inst.GetComponentsInChildren<Renderer>()) r.sharedMaterial = m;
        // head hit point = centre of the lowest 30 % of the model
        pts = Pts(inst); Bnds(pts, out mn, out mx); float h = mx.y - mn.y;
        Vector3 hc = Vector3.zero; int n = 0; hmn = new Vector3(1e9f, 1e9f, 1e9f); hmx = -hmn;
        for (int i = 0; i < pts.Count; i++) if (pts[i].y <= mn.y + 0.3f * h) { hc += pts[i]; n++; hmn = Vector3.Min(hmn, pts[i]); hmx = Vector3.Max(hmx, pts[i]); }
        hc /= Mathf.Max(n, 1); he = hmx - hmn;
        hitR = 0.5f * Mathf.Max(he.x, Mathf.Max(he.y, he.z)) * 0.9f;
        var headGO = new GameObject("HeadHit"); headGO.transform.SetParent(piv, false); headGO.transform.position = hc;
        var lg = headGO.AddComponent<Light>(); lg.type = LightType.Point; lg.color = new Color(0.3f, 0.6f, 1f); lg.range = 5f; lg.intensity = 3f;
        return headGO.transform;
    }

    void BuildAtmosphere()
    {
        var cm = Camera.main;
        if (cm != null) { cm.clearFlags = CameraClearFlags.SolidColor; cm.backgroundColor = new Color(0.55f, 0.78f, 0.95f); cm.farClipPlane = 1200f; }
        RenderSettings.fog = true; RenderSettings.fogMode = FogMode.Linear; RenderSettings.fogColor = new Color(0.72f, 0.86f, 0.96f);
        RenderSettings.fogStartDistance = 60f; RenderSettings.fogEndDistance = 380f;
        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat; RenderSettings.ambientLight = new Color(0.62f, 0.66f, 0.72f);
        foreach (var l in FindObjectsByType<Light>(FindObjectsSortMode.None))
            if (l.type == LightType.Directional) { l.color = new Color(1f, 0.96f, 0.86f); l.intensity = 1.25f; l.transform.rotation = Quaternion.Euler(48f, -28f, 0f); l.shadows = LightShadows.Soft; }
        var sun = Prim(PrimitiveType.Sphere, "Sun", new Vector3(-70f, 95f, courseLength + 230f), Vector3.one * 26f, new Color(1f, 0.95f, 0.7f));
        var sm = sun.GetComponent<Renderer>().material; sm.EnableKeyword("_EMISSION"); if (sm.HasProperty("_EmissionColor")) sm.SetColor("_EmissionColor", new Color(1f, 0.9f, 0.5f) * 3f);
    }

    void BuildTrees()
    {
        var rnd = new System.Random(randomSeed);
        Color[] leaf = { new Color(.16f, .45f, .18f), new Color(.22f, .52f, .20f), new Color(.12f, .38f, .16f), new Color(.30f, .58f, .22f) };
        for (int i = 0; i < treeCount; i++)
        {
            float side = rnd.NextDouble() < 0.5 ? -1f : 1f;
            float x = side * (courseWidth * 0.5f + R(rnd, 3.5f, 26f)), z = R(rnd, -20f, courseLength + 110f), h = R(rnd, 3f, 6.5f), r = R(rnd, 1.6f, 2.8f);
            Color lc = leaf[rnd.Next(leaf.Length)];
            Prim(PrimitiveType.Cylinder, "Trunk", new Vector3(x, h * 0.35f, z), new Vector3(0.35f, h * 0.35f, 0.35f), new Color(.36f, .24f, .14f));
            Prim(PrimitiveType.Sphere, "Leaves", new Vector3(x, h * 0.85f, z), new Vector3(r * 1.5f, r * 1.4f, r * 1.5f), lc);
            Prim(PrimitiveType.Sphere, "Leaves", new Vector3(x + 0.5f, h * 1.1f, z + 0.3f), new Vector3(r, r, r), lc);
        }
        Color[] fl = { new Color(.95f, .25f, .3f), new Color(1f, .85f, .2f), Color.white, new Color(.7f, .4f, .95f) };
        for (int i = 0; i < 70; i++)
        {
            float side = rnd.NextDouble() < 0.5 ? -1f : 1f;
            float x = side * (courseWidth * 0.5f + R(rnd, 0.7f, 3.5f)), z = R(rnd, -5f, courseLength + 20f);
            if (i % 3 == 0) Prim(PrimitiveType.Sphere, "Bush", new Vector3(x, 0.3f, z), new Vector3(R(rnd, .8f, 1.4f), R(rnd, .5f, .8f), R(rnd, .8f, 1.4f)), new Color(.18f, .46f, .2f));
            else Prim(PrimitiveType.Sphere, "Flower", new Vector3(x, 0.12f, z), Vector3.one * 0.22f, fl[rnd.Next(fl.Length)]);
        }
    }

    void BuildHills()
    {
        var rnd = new System.Random(randomSeed + 1);
        for (int i = 0; i < 16; i++)      // distant mountains
        {
            float x = -300f + i * 40f + R(rnd, 0, 20f), z = courseLength + R(rnd, 190f, 320f), w = R(rnd, 90f, 170f), h = R(rnd, 40f, 100f);
            Color c = Color.Lerp(new Color(.30f, .45f, .40f), new Color(.45f, .55f, .62f), (float)rnd.NextDouble());
            Prim(PrimitiveType.Sphere, "Hill", new Vector3(x, h * 0.1f, z), new Vector3(w, h, w * 0.8f), c);
            if (h > 70f) Prim(PrimitiveType.Sphere, "SnowCap", new Vector3(x, h * 0.5f, z), new Vector3(w * 0.35f, h * 0.28f, w * 0.3f), new Color(.95f, .97f, 1f));
        }
        for (int i = 0; i < 12; i++)      // side hills
        {
            float s = i % 2 == 0 ? -1f : 1f, x = s * R(rnd, 90f, 200f), z = R(rnd, 0f, courseLength + 250f), w = R(rnd, 50f, 90f), h = R(rnd, 14f, 30f);
            Prim(PrimitiveType.Sphere, "SideHill", new Vector3(x, h * 0.1f - 2f, z), new Vector3(w, h, w), new Color(.26f, .50f, .26f));
        }
    }

    void BuildClouds()
    {
        var rnd = new System.Random(randomSeed + 2);
        for (int i = 0; i < 16; i++)
        {
            var cloud = new GameObject("Cloud").transform; cloud.SetParent(root, false);
            Vector3 c0 = new Vector3(R(rnd, -200f, 200f), R(rnd, 60f, 90f), R(rnd, 40f, 330f)); int puffs = 4 + rnd.Next(3);
            for (int p = 0; p < puffs; p++)
                Prim(PrimitiveType.Sphere, "Puff", c0 + new Vector3(p * 7f - puffs * 3f, R(rnd, 0, 3f), R(rnd, 0, 4f)), new Vector3(R(rnd, 12f, 18f), R(rnd, 6f, 9f), 10f), Color.white, cloud);
            cloud.gameObject.AddComponent<CloudDrift>().speed = R(rnd, 0.6f, 1.4f);
        }
    }

    void BuildGate(float z, string label, Color banner)
    {
        float hw = courseWidth * 0.5f + 0.6f; Color pillar = new Color(.85f, .85f, .88f);
        Prim(PrimitiveType.Cylinder, "Pillar", new Vector3(-hw, 2.2f, z), new Vector3(0.45f, 2.2f, 0.45f), pillar);
        Prim(PrimitiveType.Cylinder, "Pillar", new Vector3(hw, 2.2f, z), new Vector3(0.45f, 2.2f, 0.45f), pillar);
        Prim(PrimitiveType.Cube, "Beam", new Vector3(0, 4.6f, z), new Vector3(hw * 2f + 0.9f, 0.9f, 0.5f), banner);
        Label(label, new Vector3(0, 4.6f, z - 0.3f), 0.6f, Color.white);
    }

    void BuildLamps()
    {
        for (int m = 5, k = 0; m < (int)courseLength; m += 10, k++)
        {
            float x = (k % 2 == 0 ? -1f : 1f) * (courseWidth * 0.5f + 0.9f);
            Prim(PrimitiveType.Cylinder, "LampPost", new Vector3(x, 1.6f, m), new Vector3(0.12f, 1.6f, 0.12f), new Color(.2f, .2f, .22f));
            Prim(PrimitiveType.Sphere, "LampLight", new Vector3(x, 3.35f, m), Vector3.one * 0.4f, new Color(1f, .92f, .6f));
        }
    }

    // ---------- runtime ----------
    void LateUpdate()
    {
        if (character == null) return;
        if (cam != null) { cam.position = character.transform.position + cameraOffset; cam.LookAt(character.transform.position + Vector3.up * 1f + Vector3.forward * 2f); }
        if (!finished && character.transform.position.z >= courseLength)
        {
            finished = true;
            result = string.Format(CultureInfo.InvariantCulture, "FINISHED {0:F1} m in {1:F1} s", character.Distance, character.ElapsedSinceStart);
            Debug.Log(result);
        }
    }

    void OnGUI()
    {
        if (character == null) return;
        float p = Mathf.Clamp01(character.transform.position.z / courseLength);
        GUI.color = new Color(0, 0, 0, 0.5f); GUI.DrawTexture(new Rect(10, 78, 300, 14), Texture2D.whiteTexture);
        GUI.color = new Color(0.2f, 0.85f, 0.3f); GUI.DrawTexture(new Rect(10, 78, 300 * p, 14), Texture2D.whiteTexture);
        GUI.color = Color.white;
        GUI.Label(new Rect(10, 94, 600, 25), finished ? result : string.Format(CultureInfo.InvariantCulture, "{0:F1} / {1:F0} m", character.transform.position.z, courseLength));
    }
}

public class CloudDrift : MonoBehaviour
{
    public float speed = 1f;
    void Update()
    {
        transform.Translate(Vector3.right * speed * Time.deltaTime, Space.World);
        if (transform.position.x > 260f) transform.position += Vector3.left * 520f;
    }
}
