# Share files without exposing your system.

![Python](https://img.shields.io/badge/Python-3.7+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.124.2-green)
![Vue.js](https://img.shields.io/badge/Vue.js-3-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

鏉╂瑦妲告稉鈧稉顏呮付鐏忓繑鏁奸柅鐘垫畱閺傚洣娆㈤崗鍙橀煩閺堝秴濮熼敍灞界殺缁狅紕鎮婇弶鍐娑撳骸鍙曢崗鍙樼瑓鏉炶棄浜ゆ惔鏇炲瀻缁備紮绱?

- **缁狅紕鎮婄粩?(姒涙顓?8800)**閿涙碍褰佹笟娑樼暚閺佸娈戠粻锛勬倞閸旂喕鍏橀敍灞藉綀 Token 娣囨繃濮㈤敍灞界紦鐠侇喕绮庨梽鎰敶缂?閺堫剚婧€鐠佸潡妫堕妴?
- **閸忣剙鍙℃稉瀣祰缁?(姒涙顓?9900)**閿?*閺嬩胶鐣濋弳鎾苟**閿涘奔绮庨幓鎰返 `/s/{token}` 娑撳娴囬幒銉ュ經閿涘本妫ゆ禒璁崇秿缁狅紕鎮婇弶鍐閿涘矂鈧倸鎮庨惄瀛樺复閺勭姴鐨犻崚鏉垮彆缂冩垯鈧?

## 閸旂喕鍏橀悧瑙勨偓?

- **閸欏矂鍣搁梾鏃傤瀲**閿涙氨澧块悶鍡欘伂閸欙綁娈х粋鑽ゎ吀閻炲棙绁︽稉搴濈瑓鏉炶姤绁﹂妴?
- **閺傚洣娆㈢粻锛勬倞**閿涙碍绁荤憴鍫㈡窗瑜版洏鈧礁鐡欓惄顔肩秿閵嗕焦鏋冩禒鏈电瑐娴肩姰鈧椒绗呮潪濮愨偓浣稿灩闂勩倧绱欓棁鈧弶鍐閿涘鈧?
- **鐎圭偞妞傞幖婊呭偍**閿涙艾缍嬮崜宥囨窗瑜版洖鍞磋箛顐︹偓鐔荤箖濠娿們鈧?
- **娑撳瓨妞傞崚鍡曢煩**閿涙矮绔撮柨顔炬晸閹存劕鐢?Token 閻ㄥ嫪澶嶉弮鏈电瑓鏉炰粙鎽奸幒銉ｂ偓?
- **棣冩暉 婢х偛宸辩紒鐔活吀**閿?
  - **鐎圭偞妞傞弮銉ョ箶**閿涙碍甯堕崚璺哄酱鐎圭偞妞傞幍鎾冲祪娑撳娴囬崝銊ょ稊閿涘牆瀵橀崥?IP閵嗕焦鏋冩禒韬测偓涔€oken閿涘鈧?
  - **濞嗏剝鏆熺紒鐔活吀**閿涙俺顔囪ぐ鏇熺槨娑擃亜鍨庢禍顐︽懠閹恒儳娈戠槐顖濐吀娑撳娴囧▎鈩冩殶閵?
  - **娑撳娴囨潪銊ㄦ姉**閿涙艾鍞寸€涙ü绻氶悾娆愭付鏉?10 濞嗏€茬瑓鏉炵晫娈戠拠锔剧矎 IP 閸滃本妞傞梻瀛樺煈閵?
- **鐠侯垰绶炵€瑰鍙?*閿涙矮寮楅弽鍏肩墡妤?`..` 缁岃儻绉洪崪宀€绮风€电鐭惧鍕剁礉缁備焦顒涚搾濠勬櫕鐠佸潡妫堕妴?

## 韫囶偊鈧喎绱戞慨?

### 1. 鐎瑰顥婃笟婵婄

```bash
pip install -r requirements.txt
```

### 2. 閻滎垰顣ㄩ柊宥囩枂

婢跺秴鍩?`.env.example` 娑?`.env`閿涘苯鑻熼幐澶愭付娣囶喗鏁奸敍?

```env
# 閸╄櫣顢呴柊宥囩枂
SHARE_DIR=D:\SharedFiles
ADMIN_TOKEN=your_secure_password_here

# 缂冩垹绮堕柊宥囩枂
PUBLIC_BASE_URL=http://example.com:9900  # 韫囧懘銆忛崠鍛儓閸楀繗顔呮径鏉戞嫲缁旑垰褰涢敍灞肩伐婵″偊绱癶ttp://your-domain.com:9900
ALLOW_OVERWRITE=false

# 闁剧偓甯撮柊宥囩枂
TOKEN_EXPIRE_HOURS=24  # 閸掑棔闊╅柧鐐复姒涙顓婚張澶嬫櫏閺堢噦绱欑亸蹇旀閿?
# 閸氬奔绔撮柧鐐复閺堚偓婢堆傜瑓鏉炶姤顐奸弫?
MAX_DOWNLOADS=10   #闂勬劕鍩楅張宥呭缁旑垰鐤勯梽鍛槱閻炲棛娈戞稉瀣祰鐠囬攱鐪板▎鈩冩殶閿涘牅绗夐崠鍛儓濞村繗顫嶉崳銊х处鐎涙ê鎳℃稉顓ㄧ礆
```

### 3. 閸氼垰濮╅張宥呭

Windows 閻滎垰顣ㄩ敍?
```bat
start_server.bat
```

闁氨鏁ら弬鐟扮础閿?
```bash
python run_server.py
```

## 鐠佸潡妫剁拠瀛樻

### 缁狅紕鎮婇悾宀勬桨 (Admin)
- **閸︽澘娼?*閿涙岸绮拋?`http://127.0.0.1:8800`
- **鐠併倛鐦?*閿涙岸顩诲▎陇绻橀崗銉╂付鏉堟挸鍙?`.env` 娑擃參鍘ょ純顔炬畱 `ADMIN_TOKEN`閵?
- **缂佺喕顓搁弻銉ф箙**閿涙艾鎮楃粩顖涘絹娓?`/api/shares` 閹恒儱褰涙笟娑氼吀閻炲棗鎲抽弻銉ф箙瑜版挸澧犻幍鈧張澶嬫た鐠哄啴鎽奸幒銉ュ挤閸忔湹绗呮潪鐣岀埠鐠伮扳偓?

### 娑撳娴囬張宥呭 (Public)
- **閸︽澘娼?*閿涙岸绮拋?`http://0.0.0.0:9900`
- **閺夊啴妾?*閿涙矮绮庨崗浣筋啅 `/s/{token}`閵嗗倷鎹㈡担鏇＄槸閸ユ崘顔栭梻顔界壌閻╊喖缍嶉妴浣侯吀閻?API 閹存牠娼▔鏇＄熅瀵板嫮娈戠悰灞艰礋閸у洩绻戦崶?`403 Forbidden`閵?

## 閸掑棔闊╅柧鐐复閺堝搫鍩?

- **閻㈢喐鍨?*閿涙氨顓搁悶鍡欘伂閻愮懓鍤垾婊冨瀻娴滎偊鎽奸幒銉⑩偓婵堟晸閹存劑鈧?
- **閸︽澘娼冮弽鐓庣础**閿涙瓪{PUBLIC_BASE_URL}/s/{token}`
- **閺堝鏅ラ張?*閿涙氨鏁?`TOKEN_EXPIRE_HOURS` 閹貉冨煑閿涘矂绮拋?24 鐏忓繑妞傞妴?
- **閹镐椒绠欓幀?*閿涙瓖oken 鐎涙ê鍋嶉崷銊ュ敶鐎涙ü鑵戦敍?*閺堝秴濮熼柌宥呮儙閸氬簼绱版径杈ㄦ櫏**閵?

## 鐎瑰鍙忔稉搴ｅ閺?

1. **闂嗘儼绉洪悾?*閿涙碍澧嶉張澶嬫惙娴ｆ粓妾洪崚璺烘躬 `SHARE_DIR` 閸欏﹤鍙剧€涙劗娲拌ぐ鏇氱瑓閵?
2. **闂冭尙鍨庨惍?*閿涙氨顓搁悶?Token 闁挎瑨顕ゆ径姘偧閸氬簼绱扮憴锕€褰?IP 娑撳瓨妞傞柨浣哥暰閿?4鐏忓繑妞傞敍澶堚偓?
3. **閸忣剛缍夐崣瀣偨**閿?900 缁旑垰褰涢崡鍏呭▏閺勭姴鐨犻崚鏉垮彆缂冩埊绱濋弨璇插毊閼板懍绡冮弮鐘崇《闁俺绻冪拠銉ь伂閸欙絾甯板ù瀣瀮娴犺泛鍨悰銊﹀灗娑撳﹣绱堕弬鍥︽閵?

## Personal Clipboard Sync

This project also connects to my personal clipboard workflow through Vclip:

- GitHub: [MasonWest/Vclip](https://github.com/MasonWest/Vclip)
- When a share link is generated, the server can also sync that link into the `clips` table used by Vclip.
- This is optional and mainly for my own daily workflow. If you do not use Vclip, the file-sharing flow still works normally.

Environment variables for the sync:

```env
SUPABASE_URL=your-supabase-project-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_CLIPS_TABLE=clips
```

## 妞ゅ湱娲扮紒鎾寸€?

```text
fastAPI/
閳规壕鏀㈤埞鈧?filesvc_api.py   # 閺嶇绺鹃柅鏄忕帆閿涘湏dmin/Public 鎼存梻鏁ょ€规矮绠熼敍?
閳规壕鏀㈤埞鈧?index.html       # 閸楁洟銆夌粻锛勬倞缁?UI
閳规壕鏀㈤埞鈧?run_server.py    # 閸欏瞼顏崣锝呮儙閸斻劌鍙嗛崣?
閳规壕鏀㈤埞鈧?start_server.bat # Windows 韫囶偅宓庨崥顖氬З
閳规壕鏀㈤埞鈧?requirements.txt # 娓氭繆绂嗛崚妤勩€?
閳规柡鏀㈤埞鈧?.env             # 閺佸繑鍔呴柊宥囩枂
```

## 鐠佺褰茬拠?

MIT License
