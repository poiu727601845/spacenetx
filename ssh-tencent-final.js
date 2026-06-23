const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const siteRoot = 'C:/Users/Administrator/WorkBuddy/2026-05-29-08-46-48/auto-site/site';

// Files to sync
const filesToSync = [
  'data/articles.json',
  'data/sectors.json',
];

// Directories to sync
const dirsToSync = [
  'index.html',
  '404.html',
  'about.html',
  'faq.html',
  'search.html',
  'tools-rank.html',
  'sitemap.xml',
  'rss.xml',
  'rss.xsl',
  'robots.txt',
  'favicon.svg',
  'favicon-og.png',
  'BingSiteAuth.xml',
  'baidu_verify_codeva-PDW8L2CNdv.html',
  'baidu_verify_codeva-cOkdGuY1KZ.html',
  'baidu_verify_codeva-gvawvw39fh.html',
  'data',
  'articles',
  'etf',
];

let syncCount = 0;
let syncErrors = 0;

function syncDir(remotePath, localPath) {
  const dir = fs.readdirSync(localPath);
  dir.forEach(file => {
    const local = path.join(localPath, file);
    const remote = `${remotePath}/${file}`;
    const stat = fs.statSync(local);
    
    if (stat.isDirectory()) {
      syncDir(`${remote}`, local);
      syncCount++;
    } else {
      // Sync individual file
      const content = fs.readFileSync(local);
      const base64 = content.toString('base64');
      conn.exec(`echo '${base64}' | base64 -d > '${remote.replace("'", "\\'")}' && echo SYNCED_${syncCount}`, (err, stdout, stderr) => {
        if (err) syncErrors++;
        else syncCount++;
      });
    }
  });
}

console.log('Starting sync to 140.143.210.199...');
conn.on('ready', () => {
  console.log('Connected to Tencent Cloud');
  
  // Upload files
  dirsToSync.forEach(dir => {
    const local = path.join(siteRoot, dir);
    const remote = `/home/ubuntu/wechat-publisher/${dir}`;
    if (fs.existsSync(local)) {
      if (fs.statSync(local).isDirectory()) {
        conn.sftp((err, sftp) => {
          if (err) { console.error(err); return; }
          
          function uploadFolder(src, dst) {
            const items = fs.readdirSync(src);
            items.forEach(item => {
              const srcPath = path.join(src, item);
              const dstPath = `${dst}/${item}`;
              const stat = fs.statSync(srcPath);
              
              if (stat.isDirectory()) {
                sftp.mkdir(dstPath, (err2) => {
                  if (!err2) uploadFolder(srcPath, dstPath);
                });
              } else {
                sftp.fastPut(srcPath, dstPath, (err3) => {
                  if (err3) console.error(`Upload error: ${dstPath}`, err3.message);
                  else console.log(`Uploaded: ${dstPath}`);
                });
              }
            });
          }
          
          uploadFolder(local, remote);
        });
      } else {
        console.log(`File ${dir} not synced (manual sync needed)`);
      }
    }
  });
  
  // Update .env
  const envContent = `WECHAT_APPID=wx8317fbdafcbcd670
WECHAT_SECRET=86b6cd8c3a546dfc14a742607b4716fe
SITE_URL=https://spacenetx.com
SITE_ROOT=/home/ubuntu/wechat-publisher/site
`;
  
  conn.exec(`cat > /home/ubuntu/wechat-publisher/.env << 'ENVEOF'
${envContent.trim()}
ENVEOF`, (err, stdout, stderr) => {
    if (err) console.error('.env update error:', err.message);
    else console.log('.env updated');
    
    console.log('\nSync complete');
    conn.exec('cd /home/ubuntu/wechat-publisher && python3 wechat_publish.py --publish 2>&1 | tail -20', (err2, stdout2, stderr2) => {
      console.log('\n=== Publish Result ===');
      if (stdout2) console.log(stdout2.toString());
      if (stderr2) console.error(stderr2.toString());
      conn.end();
    });
  });
}).connect({
  host: '140.143.210.199',
  port: 22,
  username: 'ubuntu',
  privateKey: fs.readFileSync(path.join(process.env.HOME, '.ssh', 'id_ed25519_tencent')),
  readyTimeout: 15000
});
