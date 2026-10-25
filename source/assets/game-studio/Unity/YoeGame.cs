using System;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
[Serializable] public class YoeGameSpec {
 public string title="Fox Adventure",genre="platformer",theme="forest",style="cartoon",projectId="";
 public int levels=1,seed=42,health=3,coins=8;public float speed=4.5f,jump=10,enemySpeed=1.2f;
}
[Serializable] public class YoeSave {public string scene;public int coins,health;public float x,y;public string[] collected;}
public class YoeGame : MonoBehaviour {
 public static YoeGame Instance;static YoeSave pending;static bool pendingPosition;static int smokeStage,smokeTransitions,smokeCoins,smokeHealth,smokeJumps;static float smokeTime;static Vector3 pausePosition;
 public YoeGameSpec spec;public int coins,health;public bool menu=true,won;public Transform player;public Vector3 checkpoint;readonly HashSet<string> collected=new HashSet<string>();float damageAt=-100;bool finishing;
 public bool Smoke{get;private set;}public bool HasMusic;
 string SaveKey=>"YOE."+(string.IsNullOrEmpty(spec.projectId)?spec.title:spec.projectId);
 void Awake(){Instance=this;Time.timeScale=1;spec=JsonUtility.FromJson<YoeGameSpec>(Resources.Load<TextAsset>("yoe-game").text);health=spec.health;Smoke=Array.Exists(Environment.GetCommandLineArgs(),s=>s=="-yoeSmoke");if(Smoke){menu=false;if(smokeStage==0)smokeTime=Time.realtimeSinceStartup;}}
 void Start(){player=GameObject.FindWithTag("Player").transform;checkpoint=player.position;if(pending!=null){Apply(pending,pendingPosition);pending=null;}var clip=Resources.Load<AudioClip>("YOEMusic");if(clip){var source=gameObject.AddComponent<AudioSource>();source.clip=clip;source.loop=true;source.volume=.2f;source.Play();HasMusic=true;}}
 void OnDestroy(){Time.timeScale=1;if(Instance==this)Instance=null;}
 void Update(){if(Input.GetKeyDown(KeyCode.Escape)&&!won)menu=!menu;Time.timeScale=menu||won?0:1;if(Smoke)SmokeTest();}
 public bool Collect(string name){string id=SceneManager.GetActiveScene().name+"/"+name;if(!collected.Add(id))return false;coins++;var clip=Resources.Load<AudioClip>("YOECoin");if(clip)AudioSource.PlayClipAtPoint(clip,player.position,.3f);return true;}
 public bool Damage(){if(menu||won||Time.time-damageAt<1)return false;damageAt=Time.time;var clip=Resources.Load<AudioClip>("YOEHurt");if(clip)AudioSource.PlayClipAtPoint(clip,player.position,.3f);var anim=player.GetComponent<Animator>();if(anim)anim.SetTrigger("hurt");health=Mathf.Max(0,health-1);if(health==0){health=spec.health;player.position=checkpoint;player.GetComponent<Rigidbody2D>().linearVelocity=Vector2.zero;}return true;}
 public void Respawn(){Damage();player.position=checkpoint;player.GetComponent<Rigidbody2D>().linearVelocity=Vector2.zero;}
 YoeSave Snapshot(string scene=null){return new YoeSave{scene=scene??SceneManager.GetActiveScene().name,coins=coins,health=health,x=player.position.x,y=player.position.y,collected=new List<string>(collected).ToArray()};}
 YoeItem[] SceneItems(){
#if UNITY_6000_6_OR_NEWER
 return FindObjectsByType<YoeItem>();
#else
 return FindObjectsByType<YoeItem>(FindObjectsSortMode.None);
#endif
 }
 void Apply(YoeSave data,bool position){coins=Mathf.Max(0,data.coins);health=Mathf.Clamp(data.health,1,spec.health);collected.Clear();foreach(string id in data.collected??new string[0])collected.Add(id);if(position&&float.IsFinite(data.x)&&float.IsFinite(data.y)){player.position=new Vector3(Mathf.Clamp(data.x,-3,37),Mathf.Clamp(data.y,-3,20),0);player.GetComponent<Rigidbody2D>().linearVelocity=Vector2.zero;}foreach(var item in SceneItems())if(item.kind=="coin"&&collected.Contains(SceneManager.GetActiveScene().name+"/"+item.name))Destroy(item.gameObject);}
 public void Save(){PlayerPrefs.SetString(SaveKey,JsonUtility.ToJson(Snapshot()));PlayerPrefs.Save();}
 public bool Load(){string raw=PlayerPrefs.GetString(SaveKey,"");if(raw=="")return false;try{var data=JsonUtility.FromJson<YoeSave>(raw);if(data==null||!SceneExists(data.scene))return false;if(data.scene!=SceneManager.GetActiveScene().name){pending=data;pendingPosition=true;Time.timeScale=1;SceneManager.LoadScene(data.scene);}else Apply(data,true);return true;}catch(Exception ex){Debug.LogWarning("Save could not be loaded: "+ex.Message);return false;}}
 bool SceneExists(string name){for(int i=0;i<SceneManager.sceneCountInBuildSettings;i++)if(Path.GetFileNameWithoutExtension(SceneUtility.GetScenePathByBuildIndex(i))==name)return true;return false;}
 public void Finish(){if(finishing||won)return;finishing=true;int i=SceneManager.GetActiveScene().buildIndex;if(i+1<SceneManager.sceneCountInBuildSettings){string next=Path.GetFileNameWithoutExtension(SceneUtility.GetScenePathByBuildIndex(i+1));pending=Snapshot(next);pendingPosition=false;Time.timeScale=1;SceneManager.LoadScene(i+1);}else{won=true;Time.timeScale=0;}}
 void Restart(){pending=null;Time.timeScale=1;SceneManager.LoadScene(0);}
 void SmokeTest(){try{float elapsed=Time.realtimeSinceStartup-smokeTime;var controller=player?player.GetComponent<YoePlayer>():null;
  if(smokeStage==0&&elapsed>1&&controller&&(spec.genre!="platformer"||controller.IsGrounded)){if(!player||!Camera.main||YoePlayer.Ticks<1)throw new Exception("Scene/physics did not start");int before=coins;if(!Collect("QA-coin")||Collect("QA-coin")||coins!=before+1)throw new Exception("Duplicate coin counted");if(!Damage()||Damage())throw new Exception("Damage cooldown failed");smokeCoins=coins;smokeHealth=health;Save();coins=999;if(!Load()||coins!=smokeCoins)throw new Exception("Save/load failed");if(!controller.QueueJump())throw new Exception("Jump request rejected by menu state");smokeStage=1;smokeTime=Time.realtimeSinceStartup;}
  else if(smokeStage==1&&elapsed>1.8f){smokeJumps=controller.JumpCount;if(spec.genre=="platformer"&&smokeJumps!=1)throw new Exception("Single jump request failed; jumps="+smokeJumps+", position="+player.position+", velocity="+player.GetComponent<Rigidbody2D>().linearVelocity+", "+controller.JumpState);menu=true;pausePosition=player.position;smokeStage=2;smokeTime=Time.realtimeSinceStartup;}
  else if(smokeStage==2&&elapsed>.4f){if(Vector3.Distance(player.position,pausePosition)>.02f)throw new Exception("Physics moved while paused");menu=false;Time.timeScale=1;smokeStage=3;smokeTime=Time.realtimeSinceStartup;if(SceneManager.GetActiveScene().buildIndex+1<SceneManager.sceneCountInBuildSettings){smokeTransitions++;Finish();}}
  else if(smokeStage==3&&elapsed>.6f){if(coins!=smokeCoins||health!=smokeHealth)throw new Exception("Progress lost between levels");if(SceneManager.GetActiveScene().buildIndex+1<SceneManager.sceneCountInBuildSettings){smokeTransitions++;smokeTime=Time.realtimeSinceStartup;Finish();}else{smokeStage=5;smokeTime=Time.realtimeSinceStartup;if(!Load())throw new Exception("Saved-scene restore failed");}}
  else if(smokeStage==5&&elapsed>.6f){if(SceneManager.GetActiveScene().buildIndex!=0||coins!=smokeCoins||health!=smokeHealth||Collect("QA-coin"))throw new Exception("Saved-scene progress/coins were not restored");ScreenCapture.CaptureScreenshot(Path.GetFullPath(Path.Combine(Application.dataPath,"../../../YOE/player-preview.png")));smokeStage=4;smokeTime=Time.realtimeSinceStartup;}
  else if(smokeStage==4&&elapsed>.4f){string report="{\"passed\":true,\"scope\":\"Runtime regression: scene load, physics, duplicate coin, damage cooldown, jump buffer, pause, save/load, cross-level progress; not a manual playthrough\",\"physicsTicks\":"+YoePlayer.Ticks+",\"jumpCount\":"+smokeJumps+",\"sceneTransitions\":"+smokeTransitions+",\"coins\":"+coins+",\"health\":"+health+"}";File.WriteAllText(Path.GetFullPath(Path.Combine(Application.dataPath,"../../../YOE/runtime-report.json")),report);Application.Quit(0);}
 }catch(Exception ex){Debug.LogException(ex);Application.Quit(3);}}
 void OnGUI(){GUI.matrix=Matrix4x4.TRS(Vector3.zero,Quaternion.identity,new Vector3(Screen.width/1280f,Screen.height/720f,1));GUI.skin.label.fontSize=24;GUI.Label(new Rect(24,18,1000,50),spec.title+"   Coins "+coins+"   Health "+health);if(menu||won){GUI.Box(new Rect(390,170,500,360),"");GUI.Label(new Rect(435,200,420,70),won?"Adventure complete!":spec.title);if(GUI.Button(new Rect(465,285,350,45),won?"Play again":"Play / Resume")){if(won)Restart();else menu=false;}if(!won){if(GUI.Button(new Rect(465,345,165,40),"Save"))Save();if(GUI.Button(new Rect(650,345,165,40),"Load"))Load();}GUI.Label(new Rect(420,415,470,70),"Arrows / WASD · Space jump\nEscape menu · Checkpoints save respawn position");}}
}
