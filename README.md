# cloudwatch-munin-node

ふとした思い付きで、munin-node から直接 AWS CloudWatch の custom metrics に持って行けたら便利かもしれずと、勉強がてらに作成してみました。

## 利用シーン

munin はお手軽にインストールできて重宝していますが、監視ポイントが多くなると munin-server で RRD 処理やグラフ生成処理の負荷が問題になります。AWS には CloudWatch というサービスがあり、metric data の蓄積・可視化・監視ができます。最近になって、custom metrics といって、ユーザ独自のデータを CloudWatch に put 出来るようになりました。そこで、各 munin-node から直接 CloudWatch にデータを put する事で、munin-server の肩代わりが出来るようになります。

ただし CloudWatch は細かなデータタイプや描画の指定ができません。このスクリプトの利用は限定的な metric item には使えるといった程度です。

(BUG) DATA TYPE (GAUGE, DERIVE, COUNTER, ABSOLUTE)の理解と扱いが出来てなかったので、なんちゃってで対応。cdef, negative とかはまだ未実装

# インストール

munin-node を導入する。

<pre>
sudo aptitude install munin-node
sudo aptitude install munin-plugins-extra
</pre>

[このサイトから](http://effbot.org/zone/socket-intro.htm) SimpleClient.py という python socket のサンプルソースを作る。

github の [loggly / loggly-watch](https://github.com/loggly/loggly-watch) から、cloudwacth.py を持ってきて、下記のpatchをあてる。

<pre>
--- cloudwatch.py.orig	2011-06-16 13:31:38.000000000 +0900
+++ cloudwatch.py	2011-06-16 08:31:11.000000000 +0900
@@ -38,7 +38,15 @@
         self.key = os.getenv('AWS_ACCESS_KEY_ID', key)
         self.secret_key = os.getenv('AWS_SECRET_ACCESS_KEY_ID', secret_key)
 
-    def putData(self, namespace='Loggly', metricname='EventCount', value=0):
-        foo = getSignedURL(self.key, self.secret_key, 'PutMetricData', {'Namespace': namespace, 'MetricData.member.1.MetricName': metricname, 'MetricData.member.1.Value': value})
+    def putData(self, namespace='Loggly', dimensionsname='InstanceId', dimensionsvalue='MyInstanceId',
+                metricname='EventCount', unit='None', value=0.0):
+        foo = getSignedURL(self.key, self.secret_key, 'PutMetricData', {
+                'Namespace': namespace,
+                'MetricData.member.1.Dimensions.member.1.Name': dimensionsname,
+                'MetricData.member.1.Dimensions.member.1.Value': dimensionsvalue,
+                'MetricData.member.1.MetricName': metricname,
+                'MetricData.member.1.Unit': unit,
+                'MetricData.member.1.Value': value})
         h = httplib2.Http()
         resp, content = h.request(foo)
+        # print content
</pre> 

cloudwatch-munin-node.py, SimpleClient.py, cloudwatch.py をアプリケーションのディレクトリに配置する。

cloudwatch-munin-node.py の QLIST という配列に munin の metric item の内で必要なものを指定する。

注意:　CloudWatch は AWS で課金されます。注意深く試して下さい。

cron に指定する

<pre>
crontab -e
4-59/5 * * * * /SOME/WHERE/cloudwatch-munin-node.py
</pre>

