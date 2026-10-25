using UnityEngine;
public class YoeEnemy : MonoBehaviour {
 Vector3 origin;public float speed=1,range=2;void Start(){origin=transform.position;}void FixedUpdate(){if(YoeGame.Instance.menu||YoeGame.Instance.won)return;transform.position=origin+Vector3.right*Mathf.Sin(Time.time*speed)*range;}
}
