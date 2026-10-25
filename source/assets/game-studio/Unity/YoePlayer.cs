using System.Collections.Generic;
using UnityEngine;
public class YoePlayer : MonoBehaviour {
 Rigidbody2D body;SpriteRenderer art;Animator animator;readonly HashSet<Collider2D> groundContacts=new HashSet<Collider2D>();readonly RaycastHit2D[] groundHits=new RaycastHit2D[8];float bufferedJump=-100,lastGrounded=-100;public static int Ticks;public int JumpCount{get;private set;}
 void Awake(){body=GetComponent<Rigidbody2D>();art=GetComponent<SpriteRenderer>();animator=GetComponent<Animator>();}
 void Update(){if(Input.GetKeyDown(KeyCode.Space))QueueJump();}
 public bool QueueJump(){if(YoeGame.Instance&&!YoeGame.Instance.menu&&!YoeGame.Instance.won){bufferedJump=Time.time;return true;}return false;}
 public bool IsGrounded{get{int count=body.Cast(Vector2.down,groundHits,.07f);for(int i=0;i<count;i++)if(groundHits[i].collider&&!groundHits[i].collider.isTrigger&&groundHits[i].normal.y>.5f)return true;return false;}}
 public string JumpState=>"buffer="+bufferedJump+", now="+Time.time+", grounded="+lastGrounded+", contacts="+groundContacts.Count+", hits="+body.Cast(Vector2.down,groundHits,.07f);
 void FixedUpdate(){Ticks++;var g=YoeGame.Instance;if(!g||g.menu||g.won)return;float x=g.Smoke?0:Input.GetAxisRaw("Horizontal");
  if(g.spec.genre=="topdown")body.linearVelocity=new Vector2(x,Input.GetAxisRaw("Vertical")).normalized*g.spec.speed;
  else{body.linearVelocity=new Vector2(x*g.spec.speed,body.linearVelocity.y);bool supported=false;int hits=body.Cast(Vector2.down,groundHits,.07f);for(int i=0;i<hits;i++)if(groundHits[i].collider&&!groundHits[i].collider.isTrigger&&groundHits[i].normal.y>.5f&&!groundHits[i].collider.GetComponent<YoeEnemy>())supported=true;if(body.linearVelocity.y<=.1f&&(supported||groundContacts.Count>0))lastGrounded=Time.time;if(Time.time-bufferedJump<=.12f&&Time.time-lastGrounded<=.1f){body.linearVelocity=new Vector2(body.linearVelocity.x,g.spec.jump);bufferedJump=-100;lastGrounded=-100;groundContacts.Clear();JumpCount++;if(animator)animator.SetTrigger("jump");}}
  if(x!=0)art.flipX=x<0;if(animator)animator.SetFloat("Speed",Mathf.Abs(body.linearVelocity.x));if(transform.position.y< -6)g.Respawn();
 }
 void OnCollisionStay2D(Collision2D c){bool supports=false;foreach(var point in c.contacts)if(point.normal.y>.5f)supports=true;if(supports)groundContacts.Add(c.collider);else groundContacts.Remove(c.collider);if(c.gameObject.GetComponent<YoeEnemy>())YoeGame.Instance.Damage();}
 void OnCollisionExit2D(Collision2D c){groundContacts.Remove(c.collider);}
 void OnTriggerEnter2D(Collider2D c){var item=c.GetComponent<YoeItem>();if(!item)return;var g=YoeGame.Instance;if(item.kind=="coin"){g.Collect(c.gameObject.name);Destroy(c.gameObject);}else if(item.kind=="checkpoint")g.checkpoint=transform.position;else if(item.kind=="exit")g.Finish();}
}
