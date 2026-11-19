using UnityEngine;

// Pendulum hammer hanging over the road: swings left-right across the path. If its head touches the player,
// the player is sent back to the start (EmgWalkingController.Hit). Created and configured by WalkingCourseBuilder.
public class SwingingHammer : MonoBehaviour
{
    public Transform pivot;             // rotates about Z (the swing)
    public Transform head;              // the hammer head (hit sphere centre)
    public EmgWalkingController player;
    public float amplitudeDeg = 50f;    // maximum swing angle each side
    public float period = 2.6f;         // seconds for one full back-and-forth
    public float phase = 0f;            // 0..1 offset so hammers are not in sync
    public float hitRadius = 0.8f;      // size of the head hit area (metres)

    void Update()
    {
        float ang = amplitudeDeg * Mathf.Sin(2f * Mathf.PI * (Time.time / period + phase));
        if (pivot != null) pivot.localRotation = Quaternion.Euler(0f, 0f, ang);
        if (player == null || head == null) return;
        Vector3 p = player.transform.position, a = p + Vector3.down * 0.9f, b = p + Vector3.up * 0.9f, h = head.position;
        Vector3 ab = b - a;
        float k = Mathf.Clamp01(Vector3.Dot(h - a, ab) / ab.sqrMagnitude);   // closest point on the body line
        float r = hitRadius + 0.35f;                                          // + body radius
        if ((h - (a + ab * k)).sqrMagnitude < r * r) player.Hit();
    }
}
