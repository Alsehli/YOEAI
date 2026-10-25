using UnityEngine;
public class YoePlayer : MonoBehaviour {
 Rigidbody2D body;SpriteRenderer art;Animator animator;public static int Ticks;bool grounded;float hurtAt;
 void Awake(){body=GetComponent<Rigidbody2D>();art=GetComponent<SpriteRenderer>();animator=GetComponent<Animator>();}
 void FixedUpdate(){Ticks++;var g=YoeGame.Instance;if(!g||g.menu||g.won){body.linearVelocity=Vector2.zero;return;}float x=Input.GetAxisRaw("Horizontal");if(g.Smoke)x=1;
  if(g.spec.genre=="topdown")body.linearVelocity=new Vector2(x,Input.GetAxisRaw("Vertical")).normalized*g.spec.speed;
  else{body.linearVelocity=new Vector2(x*g.spec.speed,body.linearVelocity.y);if((Input.GetKey(KeyCode.Space)||g.Smoke)&&grounded){body.linearVelocity=new Vector2(body.linearVelocity.x,g.spec.jump);grounded=false;if(animator)animator.SetTrigger("jump");}}
  if(x!=0)art.flipX=x<0;if(animator)animator.SetFloat("Speed",Mathf.Abs(body.linearVelocity.x));if(transform.position.y< -6)g.Respawn();
 }
 void OnCollisionStay2D(Collision2D c){foreach(var point in c.contacts)if(point.normal.y>.5f)grounded=true;}
 void OnCollisionExit2D(Collision2D c){grounded=false;}
 void OnCollisionEnter2D(Collision2D c){if(c.gameObject.GetComponent<YoeEnemy>()&&Time.time-hurtAt>1){hurtAt=Time.time;YoeGame.Instance.Damage();}}
 void OnTriggerEnter2D(Collider2D c){var item=c.GetComponent<YoeItem>();if(!item)return;var g=YoeGame.Instance;if(item.kind=="coin"){g.Collect();Destroy(c.gameObject);}else if(item.kind=="checkpoint")g.checkpoint=transform.position;else if(item.kind=="exit")g.Finish();}
}
