using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// Project 9: builds the game scene Assets/Scenes/EMGWalking.unity.
// Runs once automatically when the project is opened and the scene does not exist yet,
// and any time from the menu bar: Project 9 > Rebuild Game Scene (run it again after adding the Mixamo files).
// It creates 'player' (capsule + EmgWalkingController, with the Mixamo character and Idle/Walk clips when found)
// and 'Course' (WalkingCourseBuilder with the Electric_hammer model), turns on Run In Background and saves the scene.
// Model files in Assets are found by name: the character's contains "character", the idle's "idle", the walk's "walk",
// the hammer's "hammer". Without a separate character file, the idle file (Mixamo "With Skin") is used as the character.
// The course itself is created at runtime by WalkingCourseBuilder.
[InitializeOnLoad]
public static class Project9SceneSetup
{
    const string ScenePath = "Assets/Scenes/EMGWalking.unity";

    static Project9SceneSetup()
    {
        EditorApplication.delayCall += () =>
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) return;
            if (!File.Exists(ScenePath)) Build();
            else if (EditorBuildSettings.scenes.Length == 0)
                EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        };
    }

    static string FindModel(Func<string, bool> match)
    {
        foreach (var guid in AssetDatabase.FindAssets("t:Model"))
        {
            var path = AssetDatabase.GUIDToAssetPath(guid);
            if (path.StartsWith("Assets/") && match(Path.GetFileNameWithoutExtension(path).ToLowerInvariant())) return path;
        }
        return null;
    }

    static void MakeHumanoid(string path)
    {
        var imp = AssetImporter.GetAtPath(path) as ModelImporter;
        if (imp != null && imp.animationType != ModelImporterAnimationType.Human) { imp.animationType = ModelImporterAnimationType.Human; imp.SaveAndReimport(); }
    }

    static AnimationClip FirstClip(string path)
    {
        foreach (var o in AssetDatabase.LoadAllAssetsAtPath(path))
        {
            var c = o as AnimationClip;
            if (c != null && !c.name.StartsWith("__preview__")) return c;
        }
        return null;
    }

    static bool HasSkin(string path)
    {
        if (path == null) return false;
        var go = AssetDatabase.LoadAssetAtPath<GameObject>(path);
        return go != null && go.GetComponentInChildren<SkinnedMeshRenderer>(true) != null;
    }

    // Mixamo clips: loop, feet on the ground (height baked), body facing forward (rotation baked); the forward motion
    // is left as root motion, which the controller does not apply, so the character walks in place.
    static void ConfigureClips(string path)
    {
        var imp = AssetImporter.GetAtPath(path) as ModelImporter;
        if (imp == null || imp.clipAnimations.Length > 0) return;      // already set up (or set by hand)
        var clips = imp.defaultClipAnimations;
        if (clips.Length == 0) return;
        foreach (var c in clips)
        {
            c.loopTime = true;
            c.lockRootRotation = true; c.keepOriginalOrientation = true;
            c.lockRootHeightY = true; c.keepOriginalPositionY = true;
            c.lockRootPositionXZ = false;
        }
        imp.clipAnimations = clips;
        imp.SaveAndReimport();
    }

    [MenuItem("Project 9/Rebuild Game Scene")]
    public static void Build()
    {
        if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
        PlayerSettings.runInBackground = true;   // keep the game running while the bridge window has focus

        string hammerPath = FindModel(n => n.Contains("hammer"));
        string charPath = FindModel(n => n == "characterm") ?? FindModel(n => n.StartsWith("character"));
        string idlePath = FindModel(n => n.Contains("idle"));
        string walkPath = FindModel(n => n.Contains("walk"));
        if (charPath == null) charPath = HasSkin(idlePath) ? idlePath : (HasSkin(walkPath) ? walkPath : null);   // Mixamo "With Skin" idle file = the character
        foreach (var p in new[] { charPath, idlePath, walkPath }) if (p != null) MakeHumanoid(p);
        foreach (var p in new[] { idlePath, walkPath }) if (p != null) ConfigureClips(p);
        if (hammerPath != null)
        {
            var imp = AssetImporter.GetAtPath(hammerPath) as ModelImporter;   // the course builder reads the hammer mesh
            if (imp != null && !imp.isReadable) { imp.isReadable = true; imp.SaveAndReimport(); }
        }

        var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);   // Main Camera + Directional Light

        // The player: a capsule centred 1 m above the start line (as in the original game), walking along +Z.
        var player = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        player.name = "player";
        player.transform.position = new Vector3(0f, 1f, 0f);
        UnityEngine.Object.DestroyImmediate(player.GetComponent<Collider>());
        var ctrl = player.AddComponent<EmgWalkingController>();
        ctrl.strideLength = 1.4f;
        if (charPath != null)
        {
            var model = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(charPath));
            model.transform.SetParent(player.transform, false);
            model.transform.localPosition = new Vector3(0f, -1f, 0f);   // feet on the ground
            player.GetComponent<MeshRenderer>().enabled = false;
            ctrl.animator = model.GetComponent<Animator>();
        }
        if (idlePath != null) ctrl.idleClip = FirstClip(idlePath);
        if (walkPath != null) ctrl.walkClip = FirstClip(walkPath);

        // The course builder creates the whole environment and the three swinging hammers when Play is pressed.
        var course = new GameObject("Course");
        var builder = course.AddComponent<WalkingCourseBuilder>();
        builder.character = ctrl;
        if (hammerPath != null) builder.hammerModel = AssetDatabase.LoadAssetAtPath<GameObject>(hammerPath);

        // Optional testing aid: SPACE = one stride, for testing without the BioRadio. Delete this object if not wanted.
        new GameObject("Keyboard test (optional)").AddComponent<KeyboardStepSimulator>();

        Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        AssetDatabase.Refresh();
        Debug.Log("Project 9: game scene built at " + ScenePath + " - press Play. Character: " + (charPath ?? "none (capsule)") +
                  ", idle: " + (idlePath ?? "none") + ", walk: " + (walkPath ?? "none") + ", hammer: " + (hammerPath ?? "built-in"));
    }
}
