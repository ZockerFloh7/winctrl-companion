/* Windows Control UI v2 */
window.winctrlPalette = [
    ['', 'Keine Kategorie', '#94a3b8'],
    ['blue', 'Blau', '#2563eb'], ['green', 'Grün', '#16a34a'],
    ['yellow', 'Gelb', '#ca8a04'], ['orange', 'Orange', '#ea580c'],
    ['red', 'Rot', '#dc2626'], ['purple', 'Violett', '#9333ea']
];
window.createCategorySelect = function(value='') {
    const select=document.createElement('select');
    select.setAttribute('aria-label','Farbkategorie'); select.className='category-select';
    for(const [id,label,color] of window.winctrlPalette) {
        const o=document.createElement('option'); o.value=id; o.textContent='● '+label; select.append(o);
    }
    select.value=window.winctrlPalette.some(x=>x[0]===value)?value:'';
    function paint() {
        select.style.setProperty('--category-color',window.winctrlPalette.find(x=>x[0]===select.value)[2]);
    }
    select.addEventListener('change',paint); paint(); return select;
};
(() => {
    function make(tag,text,cls) {
        const e=document.createElement(tag);
        if(text!==undefined)e.textContent=text;
        if(cls)e.className=cls;
        return e;
    }
    const header=document.querySelector('header');
    if(header&&!document.querySelector('.brand-home')) {
        const brand=make('a',undefined,'brand-home');brand.href='/';brand.title='Zur Hauptseite';
        const title=make('span','Windows Control');brand.append(title);
        // Logo URL is supplied only when an actual image has been installed.
        if(window.winctrlLogoUrl) {
            const img=make('img');img.alt='';img.src=window.winctrlLogoUrl;
            img.onerror=()=>img.remove();brand.prepend(img);
        }
        header.prepend(brand);
    }
    const page=location.pathname;
    if(page==='/') {
        document.body.classList.add('page-actions');
        const heading=header.querySelector('h1');if(heading)heading.textContent='Aktionen';
    } else if(page==='/settings') {
        document.body.classList.add('page-settings');
        const heading=header.querySelector('h1');if(heading)heading.textContent='Einstellungen';
    } else if(page.startsWith('/editor/'))document.body.classList.add('page-editor');
    for(const p of document.querySelectorAll('p.muted'))if(p.textContent.startsWith('Play startet den Test im Worker.'))p.remove();

    function logFilter(box) {
        const bar=make('div',undefined,'toolbar log-filters');
        const level=make('select');level.setAttribute('aria-label','Log-Level filtern');
        for(const [text,value] of [['Alle Level',''],['Debug','DEBUG'],['Info','INFO'],['Warnungen','WARNING'],['Fehler','ERROR']]) {
            const o=make('option',text);o.value=value;level.append(o);
        }
        const search=make('input');search.type='search';search.placeholder='Log durchsuchen …';
        const count=make('span','','muted');bar.append(level,search,count);box.before(bar);
        let raw=box.textContent;
        const matches=(text,kind='')=>(!level.value||kind===level.value||new RegExp('(?:^|\\s)'+level.value+'(?:\\s|$)').test(text))&&text.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());
        function render() {
            if(box.id==='runLog') {
                let shown=0;
                for(const row of box.children){row.hidden=!matches(row.textContent,row.className.replace('log',''));if(!row.hidden)shown++;}
                count.textContent=shown+' Einträge';
            } else {
                const rows=raw.split('\n').filter(line=>matches(line));box.textContent=rows.join('\n');observer.takeRecords();
                count.textContent=rows.filter(Boolean).length+' Einträge';
            }
        }
        const observer=new MutationObserver(()=>{if(box.id!=='runLog')raw=box.textContent;render();});
        observer.observe(box,{childList:true,subtree:true,characterData:true});level.onchange=render;search.oninput=render;render();
    }
    for(const box of document.querySelectorAll('#logs,#runLog'))logFilter(box);

    if(page==='/') {
        const form=document.querySelector('form.toolbar');
        const category=createCategorySelect();category.id='newCategory';form.insertBefore(category,form.querySelector('button'));
        const filters=make('div',undefined,'toolbar');
        const search=make('input');search.type='search';search.placeholder='Aktionen suchen …';
        const color=createCategorySelect();color.options[0].textContent='Alle Farben';
        filters.append(search,color);document.querySelector('table').parentElement.before(filters);
        function apply() {
            const query=search.value.toLocaleLowerCase();
            for(const row of document.querySelectorAll('#actions tr')) {
                const text=[...row.querySelectorAll('input')].map(e=>e.value).join(' ').toLocaleLowerCase();
                const selected=row.querySelector('.category-select');
                row.classList.toggle('filtered-out',!text.includes(query)||(!!color.value&&selected?.value!==color.value));
            }
        }
        search.oninput=apply;color.addEventListener('change',apply);
        document.getElementById('actions').addEventListener('change',apply);
        new MutationObserver(apply).observe(document.getElementById('actions'),{childList:true});
    }
    if(page==='/settings') {
        const main=document.querySelector('main');
        const section=make('section',undefined,'card whitelist-card');
        section.append(make('h2','IP-Whitelist'));
        const label=make('label');const enabled=make('input');enabled.type='checkbox';
        label.append(enabled,document.createTextNode(' Nur freigegebene IP-Adressen zulassen'));
        const entries=make('textarea');entries.rows=5;entries.placeholder='Eine IP oder ein CIDR-Netz pro Zeile';entries.setAttribute('aria-label','Freigegebene IP-Adressen und Netze');
        const save=make('button','Whitelist speichern','primary');
        section.append(label,entries,make('p','Token bleibt zusätzlich erforderlich. Aktiv + leere Liste sperrt alle Kommandoserver-Clients. Die lokale Verwaltung bleibt erreichbar.','muted'),save);
        section.append(make('h3','Zuletzt gesehene Clients'),make('p','Kein Netzwerk-Scan. Angezeigt wird die Quell-IP einer Anfrage. Hinter NAT/Proxy können mehrere Geräte dieselbe IP haben.','muted'));
        const refresh=make('button','Clientliste aktualisieren');const clients=make('div',undefined,'client-grid');
        section.append(refresh,clients);
        const cards=[...main.querySelectorAll(':scope > section.card')];
        const byTitle=text=>cards.find(c=>c.querySelector('h2')?.textContent.includes(text));
        for(const card of [byTitle('Kommandoserver'),byTitle('Autostart'),section,byTitle('Zentrales Log')])if(card)main.append(card);
        async function load() {
            const d=await api('/api/settings');enabled.checked=!!d.settings.ip_whitelist_enabled;entries.value=(d.settings.ip_whitelist||[]).join('\n');
        }
        async function devices() {
            try {
                const rows=await api('/api/clients');clients.replaceChildren();
                if(!rows.length)clients.append(make('p','Noch keine Clients gesehen.'));
                const selected=new Set(entries.value.split('\n').map(x=>x.trim()).filter(Boolean));
                for(const row of rows) {
                    const card=make('article',undefined,'client-card');
                    const top=make('div',undefined,'client-card-top');
                    top.append(make('strong',row.ip,'client-ip'),make('span',row.authenticated?'Token gültig':'Token nicht bestätigt',row.authenticated?'client-state trusted':'client-state'));
                    const seen=make('div',undefined,'client-seen');seen.append(make('span','Zuletzt gesehen'),make('time',new Date(row.last_seen).toLocaleString()));
                    const add=make('button',selected.has(row.ip)?'Bereits eingetragen':'Zur Whitelist hinzufügen',selected.has(row.ip)?'':'primary');
                    add.disabled=selected.has(row.ip);
                    add.onclick=()=>{const set=new Set(entries.value.split('\n').map(x=>x.trim()).filter(Boolean));set.add(row.ip);entries.value=[...set].join('\n');add.textContent='Eingetragen – noch speichern';add.disabled=true;};
                    card.append(top,seen,add);clients.append(card);
                }
            }catch(e){notify(e.message,{kind:'error'});}
        }
        save.onclick=async()=>{
            save.disabled=true;
            try{await api('/api/settings',jsonRequest('POST',{ip_whitelist_enabled:enabled.checked,ip_whitelist:entries.value.split('\n').map(x=>x.trim()).filter(Boolean)}));await load();await devices();notify('Whitelist gespeichert.',{kind:'success'});}
            catch(e){notify(e.message,{kind:'error'});}finally{save.disabled=false;}
        };
        refresh.onclick=devices;load().then(devices).catch(e=>notify(e.message,{kind:'error'}));
    }
    if(page.startsWith('/editor/')) {
        const main=document.querySelector('main');const box=document.getElementById('runLog');
        if(main&&box) {
            const panel=box.closest('section');panel.classList.add('editor-log-panel');
            const collapse=[...panel.querySelectorAll('button')].find(b=>b.getAttribute('onclick')?.includes('toggleLog'));
            function update() {
                panel.classList.toggle('log-collapsed',box.hidden);
                if(collapse){collapse.setAttribute('aria-expanded',String(!box.hidden));collapse.textContent=box.hidden?'Protokoll ausklappen':'Protokoll einklappen';}
                requestAnimationFrame(()=>{if(window.Blockly&&typeof workspace!=='undefined'&&workspace)Blockly.svgResize(workspace);});
            }
            new MutationObserver(update).observe(box,{attributes:true,attributeFilter:['hidden']});
            new ResizeObserver(updateSize).observe(document.getElementById('blocklyDiv'));
            function updateSize(){if(window.Blockly&&typeof workspace!=='undefined'&&workspace)Blockly.svgResize(workspace);}
            update();
        }
    }
})();
