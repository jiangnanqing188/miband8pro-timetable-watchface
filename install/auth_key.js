// 在 https://watchface.zepp.com/ 登录后，按 F12 打开 Console，整段粘贴回车
// 来源：Gadgetbridge 文档 https://gadgetbridge.org/basics/pairing/huami-xiaomi-server/
// 作用：从 Zepp 账号里取出设备的 auth_key（16 字节，32 位 hex）
const zeppCookie = document.cookie.match("hm-user-login-info=(.*?);")?.[1]?.replaceAll("%2C", ",");
userCredentials = JSON.parse(decodeURI(zeppCookie))["token_info"];
userCredentials["user_id"] = document.cookie.match("userid=(.*?);")?.[1]?.replaceAll("%2C", ",");
userCredentials["app_token"] = document.cookie.match("apptoken=(.*?);")?.[1]?.replaceAll("%2C", ",");
if (!userCredentials["user_id"]) {
  throw new Error("没登录，先去 https://watchface.zepp.com/ 登录同一账号");
}
const userId = userCredentials["user_id"];
fetch(`https://api-mifit-us3.zepp.com/users/${userId}/devices?` + new URLSearchParams({
  "appid": "2882303761517383915", "channel": "play", "enableMultiDevice": "true",
  "device_type": "android_phone", "cv": "151262_8.7.1-play", "device": "android_33",
  "v": "2.0", "lang": "en_US", "country": "US",
}), { method: "GET", headers: { apptoken: userCredentials["app_token"] } })
  .then(r => r.json())
  .then(j => {
    (j.items || []).forEach(d => {
      console.log("设备:", d.device_name || d.device_mac, "| MAC:", d.mac_address,
                  "| auth_key:", d.auth_key || d.authKey || "(这条没有，看下一条)");
    });
  });
