(function(){
  const root = window.parent && window.parent.document ? window.parent.document : document;
  function markFolderV2(){
    try{
      root.documentElement.classList.add('emb-v2-folder-ui');
      const app = root.querySelector('.stApp');
      if(app){ app.setAttribute('data-turboemb-ui','v2-folder'); }
      const uploaders = Array.from(root.querySelectorAll('[data-testid="stFileUploader"]'));
      uploaders.forEach((node) => node.setAttribute('data-folder-ready','true'));
    }catch(e){}
  }
  markFolderV2();
  try{
    const observer = new MutationObserver(markFolderV2);
    observer.observe(root.body, {childList:true, subtree:true});
  }catch(e){}
  root.addEventListener('keydown', function(ev){
    if(!ev.altKey) return;
    const labels = ['Dashboard','Import / Scan','Library','Image Search  BETA','Convert to Image'];
    const map = {'1':0,'2':1,'3':2,'4':3,'5':4};
    if(!(ev.key in map)) return;
    const radios = Array.from(root.querySelectorAll('label[data-baseweb="radio"]'));
    const label = labels[map[ev.key]];
    const target = radios.find(r => (r.innerText || '').includes(label));
    if(target){ ev.preventDefault(); target.click(); }
  }, true);
})();
