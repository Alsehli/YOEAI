using System;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;

[Serializable] public class YoeGameSpec {
 public string title="Fox Adventure",genre="platformer",theme="forest",style="cartoon";
 public int levels=1,seed=42,health=3,coins=8; public float speed=4.5f,jump=10,enemySpeed=1.2f;
}
public class YoeGame : MonoBehaviour {
 public static YoeGame Instance; public YoeGameSpec spec; public int coins,health; public bool menu=true,won; public Transform player; public Vector3 checkpoint;
 public bool Smoke {get;private set;} float smokeStart; int smokeStep; public bool HasMusic;
 void Awake(){Instance=this;spec=JsonUtility.FromJson<YoeGameSpec>(Resources.Load<TextAsset>("yoe-game").text);health=spec.health;Smoke=Array.Exists(Environment.GetCommandLineArgs(),s=>s=="-yoeSmoke");if(Smoke)menu=false;smokeStart=Time.realtimeSinceStartup;}
 void Start(){player=GameObject.FindWithTag("Player").transform;checkpoint=player.position;var clip=Resources.Load<AudioClip>("YOEMusic");if(clip){var source=gameObject.AddComponent<AudioSource>();source.clip=clip;source.loop=true;source.volume=.2f;source.Play();HasMusic=true;}}
 void Update(){if(Input.GetKeyDown(KeyCode.Escape))menu=!menu;if(!Smoke)return;try{
  if(Time.realtimeSinceStartup-smokeStart<1)return;
  if(smokeStep==0){if(!player||!Camera.main)throw new Exception("Missing player or camera");Collect();Damage();Save();Load();smokeStep++;}
  if(Time.realtimeSinceStartup-smokeStart>3){if(YoePlayer.Ticks<1)throw new Exception("Physics did not tick");var path=Path.Combine(Application.dataPath,"../../../YOE/runtime-report.json");File.WriteAllText(Path.GetFullPath(path),"{\"passed\":true,\"scope\":\"Player launch, scene load, physics ticks, coin, damage, save/load; not full gameplay playthrough\",\"physicsTicks\":"+YoePlayer.Ticks+",\"coins\":"+coins+",\"health\":"+health+"}");Application.Quit(0);}
 }catch(Exception ex){Debug.LogException(ex);Application.Quit(3);}}
 public void Collect(){coins++;var clip=Resources.Load<AudioClip>("YOECoin");if(clip)AudioSource.PlayClipAtPoint(clip,player.position,.3f);} public void Damage(){var clip=Resources.Load<AudioClip>("YOEHurt");if(clip)AudioSource.PlayClipAtPoint(clip,player.position,.3f);var anim=player.GetComponent<Animator>();if(anim)anim.SetTrigger("hurt");health--;if(health<=0){health=spec.health;player.position=checkpoint;}}
 public void Respawn(){Damage();player.position=checkpoint;var rb=player.GetComponent<Rigidbody2D>();rb.linearVelocity=Vector2.zero;}
 public void Save(){PlayerPrefs.SetString("YOE."+spec.title,JsonUtility.ToJson(new YoeSave{scene=SceneManager.GetActiveScene().name,coins=coins,health=health,x=player.position.x,y=player.position.y}));PlayerPrefs.Save();}
 public void Load(){string data=PlayerPrefs.GetString("YOE."+spec.title,"");if(data=="")return;var saved=JsonUtility.FromJson<YoeSave>(data);coins=saved.coins;health=Mathf.Clamp(saved.health,1,spec.health);if(saved.scene==SceneManager.GetActiveScene().name)player.position=new Vector3(saved.x,saved.y,0);}
 public void Finish(){int i=SceneManager.GetActiveScene().buildIndex;if(i+1<SceneManager.sceneCountInBuildSettings)SceneManager.LoadScene(i+1);else won=true;}
 void OnGUI(){GUI.matrix=Matrix4x4.TRS(Vector3.zero,Quaternion.identity,new Vector3(Screen.width/1280f,Screen.height/720f,1));GUI.skin.label.fontSize=24;GUI.Label(new Rect(24,18,900,50),spec.title+"   Coins "+coins+"   Health "+health);if(menu||won){GUI.Box(new Rect(390,170,500,360),"");GUI.Label(new Rect(435,200,420,70),won?"Adventure complete!":spec.title);if(GUI.Button(new Rect(465,285,350,45),"Play / Resume")){won=false;menu=false;}if(GUI.Button(new Rect(465,345,165,40),"Save"))Save();if(GUI.Button(new Rect(650,345,165,40),"Load"))Load();GUI.Label(new Rect(420,415,470,70),"Arrows / WASD · Space jump\nEscape menu · Checkpoints save respawn position");}}
}
[Serializable] public class YoeSave {public string scene;public int coins,health;public float x,y;}
