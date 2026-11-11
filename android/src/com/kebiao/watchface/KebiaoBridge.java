package com.kebiao.watchface;

import android.app.Activity;
import android.content.ContentValues;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

/** 给网页用的桥：保存生成的表盘文件到系统下载目录 */
public class KebiaoBridge {

    private final Activity act;

    public KebiaoBridge(Activity a) {
        this.act = a;
    }

    @JavascriptInterface
    public String saveFile(String base64, String filename) {
        try {
            byte[] data = Base64.decode(base64, Base64.DEFAULT);
            if (Build.VERSION.SDK_INT >= 29) {
                ContentValues cv = new ContentValues();
                cv.put(MediaStore.MediaColumns.DISPLAY_NAME, filename);
                cv.put(MediaStore.MediaColumns.MIME_TYPE, "application/octet-stream");
                cv.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                Uri uri = act.getContentResolver()
                        .insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                if (uri == null) return "ERR:无法创建文件";
                OutputStream os = act.getContentResolver().openOutputStream(uri);
                if (os == null) return "ERR:无法写入";
                os.write(data);
                os.close();
                return "OK:Download/" + filename + ":" + data.length;
            }
            File dir = Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_DOWNLOADS);
            if (!dir.exists()) dir.mkdirs();
            File f = new File(dir, filename);
            FileOutputStream fos = new FileOutputStream(f);
            fos.write(data);
            fos.close();
            return "OK:" + f.getAbsolutePath() + ":" + data.length;
        } catch (Throwable t) {
            return "ERR:" + t.getClass().getSimpleName() + " " + t.getMessage();
        }
    }

    @JavascriptInterface
    public void toast(String msg) {
        Toast.makeText(act, msg, Toast.LENGTH_LONG).show();
    }

    @JavascriptInterface
    public String version() { return "1.0"; }
}
