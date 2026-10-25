using UnityEngine;
public class YoeCamera : MonoBehaviour {
 void LateUpdate(){var g=YoeGame.Instance;if(g&&g.player){var p=g.player.position;transform.position=Vector3.Lerp(transform.position,new Vector3(Mathf.Clamp(p.x,7,25),g.spec.genre=="topdown"?Mathf.Clamp(p.y,0,9):2,-10),.1f);}}
}
