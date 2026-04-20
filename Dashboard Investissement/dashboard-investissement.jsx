import { useState, useMemo, useCallback, useRef } from "react";
import { PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar, ResponsiveContainer, Area, AreaChart } from "recharts";

const COLORS = ["#8b5cf6","#06b6d4","#f59e0b","#ec4899","#10b981","#3b82f6","#f97316","#a855f7","#14b8a6","#f43f5e"];
const LOAN_COLORS = ["#ef4444","#f97316","#eab308"];
const MONTH_NAMES = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"];

const DEFAULT_DATA = {
  platforms:["RMM","Lendermarket","Revolut","Mintos","Robot Trading","RealT","Debitum"],
  months:["2023-11","2023-12","2024-01","2024-02","2024-03","2024-04","2024-05","2024-06","2024-07","2024-08","2024-09","2024-10","2024-11","2024-12","2025-01","2025-02","2025-03","2025-04","2025-05","2025-06","2025-07","2025-08","2025-09","2025-10","2025-11","2025-12"],
  interests:{
    "RMM":[24,218,186,96,80,20,8,29,0,0,0,0,0,0,30,30,30,30,30,100,100,100,100,10,10,8],
    "Lendermarket":[42,148,124,276,176,110,217,138,188,148,105,167,134,140,155,0,0,30,120,172,174,211,220,287,272,282],
    "Revolut":[3,27,33,64,57,51,51,0,0,0,0,0,0,15,92,92,90,50,32,34,26,25,25,25,25,10],
    "Mintos":[35,131,165,159,147,150,166,153,181,147,152,157,199,190,200,131,121,105,22,23,10,3,0,0,0,0],
    "Robot Trading":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    "RealT":[245,252,253,253,255,240,240,240,240,240,240,240,250,250,250,250,220,220,220,220,220,220,30,30,30,30],
    "Debitum":[4,92,154,238,305,338,413,401,422,415,413,464,509,674,675,602,512,539,611,694,730,663,729,729,663,691]
  },
  principal:{
    "RMM":[25000,10000,5699,5567,2598,0,1000,1603,1620,1693,207,2191,2382,2382,15000,15000,14200,14200,14200,14200,14200,14200,10000,1055,1055,1055],
    "Lendermarket":[14000,14000,12094,12221,12397,12275,12084,11754,9126,9274,9379,9546,10210,10210,12332,0,0,11700,12000,12543,12671,12906,12906,19426,19685,21780],
    "Revolut":[2000,4000,5815,5858,5915,0,0,0,2700,3269,3269,0,3269,3269,39984,39984,36000,26500,27838,21000,19500,20700,13000,6000,5000,700],
    "Mintos":[13000,12500,12087,12170,12332,13426,13709,13864,14031,14963,15417,18796,19047,19047,9769,9769,10015,3130,1332,894,904,247,247,206,206,206],
    "Robot Trading":[0,0,0,0,0,0,0,8284,7650,6007,6453,6453,0,0,0,0,5000,0,0,0,0,0,700,2000,0,5000],
    "RealT":[31500,31500,29123,29123,29395,29800,29500,30147,29377,29500,29700,29700,29950,29950,29950,29950,29500,28000,28000,28000,28000,28000,32000,32000,32000,32000],
    "Debitum":[0,15000,22986,23334,27372,34681,34915,34930,32913,32809,32910,43558,48513,49000,52994,52994,40642,51155,53701,60518,61336,61336,61339,60341,60341,54561]
  },
  loanNames:["Emprunt Younited","Emprunt Revolut","Emprunt RMM"],
  loanMonthlyPayments:{"Emprunt Younited":747,"Emprunt Revolut":0,"Emprunt RMM":0},
  loans:{
    "Emprunt Younited":[38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300,38300],
    "Emprunt Revolut":[17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700,17700],
    "Emprunt RMM":[5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200,5200]
  }
};

function fmtMonth(ym) {
  const [y, m] = ym.split("-");
  return MONTH_NAMES[parseInt(m,10)-1] + " " + y;
}
function nextMonth(ym) {
  const [y, m] = ym.split("-").map(Number);
  return (m===12?y+1:y) + "-" + String(m===12?1:m+1).padStart(2,"0");
}

const Card = ({children,className=""}) => (
  <div className={"rounded-2xl p-5 "+className} style={{background:"linear-gradient(135deg,rgba(30,20,60,0.95),rgba(20,15,45,0.98))",border:"1px solid rgba(139,92,246,0.15)",boxShadow:"0 8px 32px rgba(0,0,0,0.3)"}}>
    {children}
  </div>
);

const StatCard = ({label,value,sub,icon,color}) => (
  <Card className="flex flex-col gap-1 min-w-0">
    <div className="flex items-center gap-2">
      <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm" style={{background:color+"22",color}}>{icon}</div>
      <span className="text-xs font-medium" style={{color:"rgba(255,255,255,0.5)"}}>{label}</span>
    </div>
    <div className="text-xl font-bold text-white mt-1 truncate">{value}</div>
    {sub && <div className="text-xs" style={{color:"rgba(255,255,255,0.4)"}}>{sub}</div>}
  </Card>
);

const CTooltip = ({active,payload,label}) => {
  if(!active||!payload?.length) return null;
  return (
    <div className="rounded-xl p-3 text-xs" style={{background:"rgba(15,10,35,0.95)",border:"1px solid rgba(139,92,246,0.3)",boxShadow:"0 8px 32px rgba(0,0,0,0.5)"}}>
      <div className="font-semibold text-white mb-2">{label}</div>
      {payload.map((p,i) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          <div className="w-2 h-2 rounded-full" style={{background:p.color}} />
          <span style={{color:"rgba(255,255,255,0.6)"}}>{p.name} :</span>
          <span className="font-semibold text-white">{typeof p.value==='number'?p.value.toLocaleString('fr-FR')+' €':p.value}</span>
        </div>
      ))}
    </div>
  );
};

const Btn = ({children,onClick,variant="primary",className=""}) => {
  const s = {
    primary:{background:"linear-gradient(135deg,#8b5cf6,#6d28d9)",color:"#fff"},
    secondary:{background:"rgba(255,255,255,0.05)",border:"1px solid rgba(255,255,255,0.1)",color:"#fff"},
    success:{background:"linear-gradient(135deg,#10b981,#059669)",color:"#fff"},
    danger:{background:"linear-gradient(135deg,#ef4444,#dc2626)",color:"#fff"},
  };
  return <button onClick={onClick} className={"px-4 py-2 rounded-lg text-xs font-medium transition-all "+className} style={s[variant]}>{children}</button>;
};

export default function Dashboard() {
  const [data, setData] = useState(DEFAULT_DATA);
  const [activeTab, setActiveTab] = useState("overview");
  const [editMonth, setEditMonth] = useState(DEFAULT_DATA.months.length-1);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({});
  const [loanFormData, setLoanFormData] = useState({});
  const [notification, setNotification] = useState(null);
  const [showAddMonth, setShowAddMonth] = useState(false);
  const fileRef = useRef(null);

  const {platforms, months, interests, principal, loanNames=[], loans={}, loanMonthlyPayments={}} = data;
  const latestIdx = months.length-1;

  const notify = (msg,type="success") => { setNotification({msg,type}); setTimeout(()=>setNotification(null),3000); };

  // === Computed ===
  const totalLoansAtIdx = useCallback((idx) =>
    loanNames.reduce((s,l) => s + (loans[l]?.[idx]||0), 0)
  , [loanNames, loans]);

  const totals = useMemo(() => {
    const totalPrincipal = platforms.reduce((s,p)=>s+(principal[p]?.[latestIdx]||0),0);
    const totalLoansCurrent = totalLoansAtIdx(latestIdx);
    const netCapital = totalPrincipal - totalLoansCurrent;
    const totalInterestsCumul = platforms.reduce((s,p)=>s+(interests[p]?.reduce((a,b)=>a+b,0)||0),0);
    const lastMonthInterest = platforms.reduce((s,p)=>s+(interests[p]?.[latestIdx]||0),0);
    const prevMonthInterest = latestIdx>0?platforms.reduce((s,p)=>s+(interests[p]?.[latestIdx-1]||0),0):0;
    const monthlyChange = prevMonthInterest>0?((lastMonthInterest-prevMonthInterest)/prevMonthInterest*100).toFixed(1):0;
    const avgMonthly = months.length>0?totalInterestsCumul/months.length:0;
    const annualYield = totalPrincipal>0?(avgMonthly*12/totalPrincipal*100).toFixed(1):0;
    const totalMonthlyPayments = loanNames.reduce((s,l)=>s+(loanMonthlyPayments[l]||0),0);
    const netMonthlyIncome = lastMonthInterest - totalMonthlyPayments;
    return {totalPrincipal,totalLoansCurrent,netCapital,totalInterestsCumul,lastMonthInterest,prevMonthInterest,monthlyChange,avgMonthly,annualYield,totalMonthlyPayments,netMonthlyIncome};
  }, [interests,principal,platforms,months,latestIdx,loanNames,loans,loanMonthlyPayments,totalLoansAtIdx]);

  const pieData = useMemo(()=>platforms.map((p,i)=>({name:p,value:principal[p]?.[latestIdx]||0,color:COLORS[i%COLORS.length]})).filter(d=>d.value>0),[principal,platforms,latestIdx]);
  const monthLabels = useMemo(()=>months.map(m=>fmtMonth(m).substring(0,8)),[months]);

  const evolutionData = useMemo(()=>months.map((m,i)=>{
    const row={name:monthLabels[i]};
    platforms.forEach(p=>{row[p]=principal[p]?.[i]||0;});
    row.Total=platforms.reduce((s,p)=>s+(principal[p]?.[i]||0),0);
    return row;
  }),[principal,platforms,months,monthLabels]);

  const interestData = useMemo(()=>months.map((m,i)=>{
    const row={name:monthLabels[i]};
    platforms.forEach(p=>{row[p]=interests[p]?.[i]||0;});
    row.Total=platforms.reduce((s,p)=>s+(interests[p]?.[i]||0),0);
    return row;
  }),[interests,platforms,months,monthLabels]);

  const cumulInterestData = useMemo(()=>{
    const c={};platforms.forEach(p=>{c[p]=0;});
    return months.map((m,i)=>{
      const row={name:monthLabels[i]};
      platforms.forEach(p=>{c[p]+=interests[p]?.[i]||0;row[p]=c[p];});
      row.Total=platforms.reduce((s,p)=>s+row[p],0);
      return row;
    });
  },[interests,platforms,months,monthLabels]);

  const interestPieData = useMemo(()=>platforms.map((p,i)=>({name:p,value:interests[p]?.reduce((a,b)=>a+b,0)||0,color:COLORS[i%COLORS.length]})).filter(d=>d.value>0),[interests,platforms]);

  // Net capital evolution (brut - emprunts)
  const netEvolutionData = useMemo(()=>months.map((m,i)=>{
    const brut = platforms.reduce((s,p)=>s+(principal[p]?.[i]||0),0);
    const dette = totalLoansAtIdx(i);
    return {name:monthLabels[i], "Capital brut":brut, Emprunts:dette, "Capital net":brut-dette};
  }),[principal,platforms,months,monthLabels,totalLoansAtIdx]);

  const loanEvolutionData = useMemo(()=>months.map((m,i)=>{
    const row={name:monthLabels[i]};
    loanNames.forEach(l=>{row[l]=loans[l]?.[i]||0;});
    row.Total=loanNames.reduce((s,l)=>s+(loans[l]?.[i]||0),0);
    return row;
  }),[loans,loanNames,months,monthLabels]);

  // === Actions ===
  const exportJSON = () => {
    const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download="data-investissement.json";a.click();
    URL.revokeObjectURL(url);
    notify("Fichier JSON exporté avec succès !");
  };

  const importJSON = (e) => {
    const file=e.target.files?.[0]; if(!file) return;
    const reader=new FileReader();
    reader.onload=(ev)=>{
      try {
        const p=JSON.parse(ev.target.result);
        if(!p.platforms||!p.months||!p.interests||!p.principal){notify("Format JSON invalide.","error");return;}
        if(!p.loanNames) p.loanNames=[];
        if(!p.loans) p.loans={};
        if(!p.loanMonthlyPayments) p.loanMonthlyPayments={};
        setData(p);setEditMonth(p.months.length-1);
        notify("Données importées : "+p.months.length+" mois, "+p.platforms.length+" plateformes");
      } catch{notify("Erreur de lecture JSON.","error");}
    };
    reader.readAsText(file);e.target.value="";
  };

  const addNewMonth = () => {
    const nm=nextMonth(months[months.length-1]);
    const nd={...data,months:[...months,nm],interests:{...interests},principal:{...principal},loans:{...loans}};
    platforms.forEach(p=>{nd.interests[p]=[...(interests[p]||[]),0];nd.principal[p]=[...(principal[p]||[]),principal[p]?.[months.length-1]||0];});
    loanNames.forEach(l=>{nd.loans[l]=[...(loans[l]||[]),loans[l]?.[months.length-1]||0];});
    setData(nd);setEditMonth(nd.months.length-1);setShowAddMonth(false);
    notify("Mois "+fmtMonth(nm)+" ajouté !");
    loadMonthFor(nd,nd.months.length-1);setShowForm(true);
  };

  const loadMonthFor = useCallback((d,idx) => {
    const fd={};d.platforms.forEach(p=>{fd[p]={interest:d.interests[p]?.[idx]??0,principal:d.principal[p]?.[idx]??0};});
    setFormData(fd);
    const ld={};(d.loanNames||[]).forEach(l=>{ld[l]=d.loans[l]?.[idx]??0;});
    setLoanFormData(ld);
  },[]);

  const loadMonth = useCallback((idx) => {loadMonthFor(data,idx);setEditMonth(idx);},[data,loadMonthFor]);

  const saveMonth = () => {
    const nd={...data,interests:{...interests},principal:{...principal},loans:{...loans}};
    platforms.forEach(p=>{
      const ia=[...(nd.interests[p]||[])],pa=[...(nd.principal[p]||[])];
      while(ia.length<=editMonth)ia.push(0);while(pa.length<=editMonth)pa.push(0);
      ia[editMonth]=Number(formData[p]?.interest)||0;pa[editMonth]=Number(formData[p]?.principal)||0;
      nd.interests[p]=ia;nd.principal[p]=pa;
    });
    loanNames.forEach(l=>{
      const la=[...(nd.loans[l]||[])];
      while(la.length<=editMonth)la.push(0);
      la[editMonth]=Number(loanFormData[l])||0;
      nd.loans[l]=la;
    });
    setData(nd);setShowForm(false);
    notify("Données de "+fmtMonth(months[editMonth])+" sauvegardées ! N'oubliez pas d'exporter le JSON.");
  };

  const fmt = v => v.toLocaleString('fr-FR')+' €';
  const fmtK = v => (v>=1000?(v/1000).toFixed(0)+'k':v)+'€';
  const pieLabel = ({name,percent}) => percent>0.03?name+" "+Math.round(percent*100)+"%":"";

  const tabs = [
    {id:"overview",label:"Vue d'ensemble"},
    {id:"interests",label:"Intérêts"},
    {id:"evolution",label:"Évolution"},
    {id:"loans",label:"Emprunts"},
    {id:"update",label:"Mise à jour"}
  ];

  return (
    <div className="min-h-screen p-4 md:p-6" style={{background:"linear-gradient(180deg,#0c0618 0%,#110b2e 50%,#0a0520 100%)",fontFamily:"'Inter',-apple-system,sans-serif"}}>
      <div className="max-w-7xl mx-auto">

        {notification && (
          <div className="fixed top-4 right-4 z-50 rounded-xl px-4 py-3 text-xs font-medium text-white shadow-lg"
            style={{background:notification.type==="error"?"linear-gradient(135deg,#ef4444,#dc2626)":"linear-gradient(135deg,#10b981,#059669)",boxShadow:"0 8px 32px rgba(0,0,0,0.4)"}}>
            {notification.msg}
          </div>
        )}

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Portfolio Dashboard</h1>
            <p className="text-sm mt-1" style={{color:"rgba(255,255,255,0.4)"}}>Suivi de vos investissements P2P & Crypto</p>
          </div>
          <div className="flex gap-1 p-1 rounded-xl" style={{background:"rgba(139,92,246,0.08)",border:"1px solid rgba(139,92,246,0.15)"}}>
            {tabs.map(t => (
              <button key={t.id} onClick={()=>setActiveTab(t.id)} className="px-3 py-2 rounded-lg text-xs font-medium transition-all"
                style={{background:activeTab===t.id?"linear-gradient(135deg,#8b5cf6,#6d28d9)":"transparent",color:activeTab===t.id?"#fff":"rgba(255,255,255,0.5)"}}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
          <StatCard label="Capital Brut" value={fmt(totals.totalPrincipal)} icon="💰" color="#8b5cf6" sub={"Sur "+platforms.filter(p=>(principal[p]?.[latestIdx]||0)>0).length+" plateformes"} />
          <StatCard label="Capital Net" value={fmt(totals.netCapital)} icon="🏦" color={totals.netCapital>=0?"#10b981":"#ef4444"} sub={"Emprunts : "+fmt(totals.totalLoansCurrent)} />
          <StatCard label="Intérêts du mois" value={fmt(totals.lastMonthInterest)} icon="📈" color="#06b6d4" sub={(totals.monthlyChange>0?"+":"")+totals.monthlyChange+"% vs mois préc."} />
          <StatCard label="Intérêts cumulés" value={fmt(totals.totalInterestsCumul)} icon="📊" color="#f59e0b" sub={"Moy. "+fmt(Math.round(totals.avgMonthly))+"/mois"} />
          <StatCard label="Revenu net mensuel" value={fmt(totals.netMonthlyIncome)} icon="⚡" color={totals.netMonthlyIncome>=0?"#10b981":"#ef4444"} sub={"Remb. "+fmt(totals.totalMonthlyPayments)+"/mois"} />
        </div>

        {/* === OVERVIEW === */}
        {activeTab==="overview" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="lg:col-span-2">
              <h3 className="text-sm font-semibold text-white mb-4">Évolution capital brut vs net</h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={netEvolutionData}>
                  <defs>
                    <linearGradient id="gBrut" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3}/><stop offset="100%" stopColor="#8b5cf6" stopOpacity={0}/></linearGradient>
                    <linearGradient id="gNet" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#10b981" stopOpacity={0.3}/><stop offset="100%" stopColor="#10b981" stopOpacity={0}/></linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                  <XAxis dataKey="name" tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}} interval={3}/>
                  <YAxis tickFormatter={fmtK} tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}}/>
                  <Tooltip content={<CTooltip/>}/>
                  <Legend wrapperStyle={{fontSize:10}}/>
                  <Area type="monotone" dataKey="Capital brut" stroke="#8b5cf6" strokeWidth={2} fill="url(#gBrut)"/>
                  <Area type="monotone" dataKey="Emprunts" stroke="#ef4444" strokeWidth={1.5} fill="none" strokeDasharray="5 5"/>
                  <Area type="monotone" dataKey="Capital net" stroke="#10b981" strokeWidth={2} fill="url(#gNet)"/>
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            <Card>
              <h3 className="text-sm font-semibold text-white mb-4">Répartition actuelle</h3>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} innerRadius={45} dataKey="value" label={pieLabel} labelLine={false} style={{fontSize:9}}>
                    {pieData.map((d,i)=><Cell key={i} fill={d.color} stroke="transparent"/>)}
                  </Pie>
                  <Tooltip content={<CTooltip/>}/>
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-2 mt-2 justify-center">
                {pieData.map((d,i)=>(<div key={i} className="flex items-center gap-1 text-xs" style={{color:"rgba(255,255,255,0.6)"}}><div className="w-2 h-2 rounded-full" style={{background:d.color}}/>{d.name}</div>))}
              </div>
            </Card>

            <Card className="lg:col-span-2">
              <h3 className="text-sm font-semibold text-white mb-4">Intérêts mensuels</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={interestData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                  <XAxis dataKey="name" tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}} interval={3}/>
                  <YAxis tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}}/>
                  <Tooltip content={<CTooltip/>}/><Legend wrapperStyle={{fontSize:10}}/>
                  {platforms.map((p,i)=><Bar key={p} dataKey={p} stackId="a" fill={COLORS[i%COLORS.length]} radius={i===platforms.length-1?[2,2,0,0]:[0,0,0,0]}/>)}
                </BarChart>
              </ResponsiveContainer>
            </Card>

            <Card>
              <h3 className="text-sm font-semibold text-white mb-4">Détails par plateforme</h3>
              <div className="space-y-3">
                {platforms.map((p,i)=>{
                  const val=principal[p]?.[latestIdx]||0,pct=totals.totalPrincipal>0?(val/totals.totalPrincipal*100).toFixed(1):0,intVal=interests[p]?.[latestIdx]||0;
                  return val>0?(
                    <div key={p}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full" style={{background:COLORS[i%COLORS.length]}}/><span style={{color:"rgba(255,255,255,0.7)"}}>{p}</span></span>
                        <span className="text-white font-medium">{fmt(val)}</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full overflow-hidden" style={{background:"rgba(255,255,255,0.05)"}}><div className="h-full rounded-full" style={{width:pct+"%",background:COLORS[i%COLORS.length]}}/></div>
                      <div className="flex justify-between text-xs mt-0.5" style={{color:"rgba(255,255,255,0.3)"}}><span>{pct}%</span><span>+{fmt(intVal)} ce mois</span></div>
                    </div>
                  ):null;
                })}
              </div>
            </Card>
          </div>
        )}

        {/* === INTERESTS === */}
        {activeTab==="interests" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="lg:col-span-2">
              <h3 className="text-sm font-semibold text-white mb-4">Intérêts cumulés par plateforme</h3>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={cumulInterestData}>
                  <defs>{platforms.map((p,i)=>(<linearGradient key={p} id={"gi"+i} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS[i%COLORS.length]} stopOpacity={0.2}/><stop offset="100%" stopColor={COLORS[i%COLORS.length]} stopOpacity={0}/></linearGradient>))}</defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                  <XAxis dataKey="name" tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}} interval={3}/>
                  <YAxis tickFormatter={fmtK} tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}}/>
                  <Tooltip content={<CTooltip/>}/><Legend wrapperStyle={{fontSize:10}}/>
                  {platforms.map((p,i)=><Area key={p} type="monotone" dataKey={p} stroke={COLORS[i%COLORS.length]} strokeWidth={1.5} fill={"url(#gi"+i+")"}/>)}
                </AreaChart>
              </ResponsiveContainer>
            </Card>
            <Card>
              <h3 className="text-sm font-semibold text-white mb-4">Répartition des intérêts totaux</h3>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart><Pie data={interestPieData} cx="50%" cy="50%" outerRadius={90} innerRadius={50} dataKey="value" label={pieLabel} labelLine={false} style={{fontSize:10}}>{interestPieData.map((d,i)=><Cell key={i} fill={d.color} stroke="transparent"/>)}</Pie><Tooltip content={<CTooltip/>}/></PieChart>
              </ResponsiveContainer>
            </Card>
            <Card>
              <h3 className="text-sm font-semibold text-white mb-4">Intérêts totaux par plateforme</h3>
              <div className="space-y-3">
                {platforms.map((p,i)=>{const total=interests[p]?.reduce((a,b)=>a+b,0)||0;const mx=Math.max(...platforms.map(pl=>interests[pl]?.reduce((a,b)=>a+b,0)||0));
                  return total>0?(<div key={p}><div className="flex justify-between text-xs mb-1"><span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full" style={{background:COLORS[i%COLORS.length]}}/><span style={{color:"rgba(255,255,255,0.7)"}}>{p}</span></span><span className="text-white font-medium">{fmt(total)}</span></div><div className="w-full h-1.5 rounded-full overflow-hidden" style={{background:"rgba(255,255,255,0.05)"}}><div className="h-full rounded-full" style={{width:(total/mx*100)+"%",background:COLORS[i%COLORS.length]}}/></div></div>):null;
                })}
              </div>
            </Card>
            <Card className="lg:col-span-2">
              <h3 className="text-sm font-semibold text-white mb-4">Évolution mensuelle des intérêts</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={interestData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                  <XAxis dataKey="name" tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}} interval={3}/>
                  <YAxis tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}}/>
                  <Tooltip content={<CTooltip/>}/><Legend wrapperStyle={{fontSize:10}}/>
                  {platforms.map((p,i)=><Line key={p} type="monotone" dataKey={p} stroke={COLORS[i%COLORS.length]} strokeWidth={1.5} dot={false}/>)}
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </div>
        )}

        {/* === EVOLUTION === */}
        {activeTab==="evolution" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="lg:col-span-2">
              <h3 className="text-sm font-semibold text-white mb-4">Évolution détaillée du capital par plateforme</h3>
              <ResponsiveContainer width="100%" height={400}>
                <AreaChart data={evolutionData}>
                  <defs>{platforms.map((p,i)=>(<linearGradient key={p} id={"ge"+i} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COLORS[i%COLORS.length]} stopOpacity={0.15}/><stop offset="100%" stopColor={COLORS[i%COLORS.length]} stopOpacity={0}/></linearGradient>))}</defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                  <XAxis dataKey="name" tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}} interval={2}/>
                  <YAxis tickFormatter={fmtK} tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}}/>
                  <Tooltip content={<CTooltip/>}/><Legend wrapperStyle={{fontSize:10}}/>
                  {platforms.map((p,i)=><Area key={p} type="monotone" dataKey={p} stroke={COLORS[i%COLORS.length]} strokeWidth={1.5} fill={"url(#ge"+i+")"} stackId="1"/>)}
                </AreaChart>
              </ResponsiveContainer>
            </Card>
            <Card>
              <h3 className="text-sm font-semibold text-white mb-4">Variation mensuelle du total</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={evolutionData.map((d,i)=>({name:d.name,variation:i>0?d.Total-evolutionData[i-1].Total:0})).slice(1)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                  <XAxis dataKey="name" tick={{fontSize:9,fill:"rgba(255,255,255,0.4)"}} interval={3}/>
                  <YAxis tickFormatter={fmtK} tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}}/>
                  <Tooltip content={<CTooltip/>}/>
                  <Bar dataKey="variation" name="Variation" radius={[3,3,0,0]}>
                    {evolutionData.slice(1).map((d,i)=>{const v=d.Total-(evolutionData[i]?.Total||0);return <Cell key={i} fill={v>=0?"#10b981":"#ef4444"}/>;
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card>
              <h3 className="text-sm font-semibold text-white mb-4">Comparaison mois actuel / précédent</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={platforms.map((p,i)=>({name:p,current:principal[p]?.[latestIdx]||0,previous:principal[p]?.[Math.max(0,latestIdx-1)]||0})).filter(d=>d.current>0||d.previous>0)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                  <XAxis type="number" tickFormatter={fmtK} tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}}/>
                  <YAxis type="category" dataKey="name" tick={{fontSize:10,fill:"rgba(255,255,255,0.5)"}} width={90}/>
                  <Tooltip content={<CTooltip/>}/><Legend wrapperStyle={{fontSize:10}}/>
                  <Bar dataKey="previous" name="Mois préc." fill="rgba(139,92,246,0.3)" radius={[0,3,3,0]}/>
                  <Bar dataKey="current" name="Mois actuel" fill="#8b5cf6" radius={[0,3,3,0]}/>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>
        )}

        {/* === LOANS === */}
        {activeTab==="loans" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Loan summary cards */}
            {loanNames.map((l,i) => {
              const current = loans[l]?.[latestIdx]||0;
              const initial = loans[l]?.[0]||current;
              const paidOff = initial - current;
              const pctPaid = initial>0?(paidOff/initial*100).toFixed(1):0;
              const monthly = loanMonthlyPayments[l]||0;
              return (
                <Card key={l}>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-3 h-3 rounded-full" style={{background:LOAN_COLORS[i%LOAN_COLORS.length]}}/>
                    <span className="text-sm font-semibold text-white">{l}</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs"><span style={{color:"rgba(255,255,255,0.5)"}}>Restant dû</span><span className="text-white font-medium">{fmt(current)}</span></div>
                    <div className="flex justify-between text-xs"><span style={{color:"rgba(255,255,255,0.5)"}}>Montant initial</span><span style={{color:"rgba(255,255,255,0.6)"}}>{fmt(initial)}</span></div>
                    <div className="flex justify-between text-xs"><span style={{color:"rgba(255,255,255,0.5)"}}>Remboursé</span><span style={{color:"#10b981"}}>{fmt(paidOff)} ({pctPaid}%)</span></div>
                    {monthly>0 && <div className="flex justify-between text-xs"><span style={{color:"rgba(255,255,255,0.5)"}}>Mensualité</span><span style={{color:"#f59e0b"}}>{fmt(monthly)}/mois</span></div>}
                    <div className="w-full h-2 rounded-full overflow-hidden mt-1" style={{background:"rgba(255,255,255,0.05)"}}>
                      <div className="h-full rounded-full" style={{width:pctPaid+"%",background:"linear-gradient(90deg,#10b981,#059669)"}}/>
                    </div>
                  </div>
                </Card>
              );
            })}

            <Card className="lg:col-span-3">
              <h3 className="text-sm font-semibold text-white mb-4">Évolution des emprunts</h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={loanEvolutionData}>
                  <defs>{loanNames.map((l,i)=>(<linearGradient key={l} id={"gl"+i} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={LOAN_COLORS[i%LOAN_COLORS.length]} stopOpacity={0.2}/><stop offset="100%" stopColor={LOAN_COLORS[i%LOAN_COLORS.length]} stopOpacity={0}/></linearGradient>))}</defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                  <XAxis dataKey="name" tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}} interval={3}/>
                  <YAxis tickFormatter={fmtK} tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}}/>
                  <Tooltip content={<CTooltip/>}/><Legend wrapperStyle={{fontSize:10}}/>
                  {loanNames.map((l,i)=><Area key={l} type="monotone" dataKey={l} stroke={LOAN_COLORS[i%LOAN_COLORS.length]} strokeWidth={1.5} fill={"url(#gl"+i+")"} stackId="1"/>)}
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            <Card className="lg:col-span-2">
              <h3 className="text-sm font-semibold text-white mb-4">Capital net vs dette totale</h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={netEvolutionData}>
                  <defs>
                    <linearGradient id="gnBrut" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.2}/><stop offset="100%" stopColor="#8b5cf6" stopOpacity={0}/></linearGradient>
                    <linearGradient id="gnNet" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#10b981" stopOpacity={0.2}/><stop offset="100%" stopColor="#10b981" stopOpacity={0}/></linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)"/>
                  <XAxis dataKey="name" tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}} interval={3}/>
                  <YAxis tickFormatter={fmtK} tick={{fontSize:10,fill:"rgba(255,255,255,0.4)"}}/>
                  <Tooltip content={<CTooltip/>}/><Legend wrapperStyle={{fontSize:10}}/>
                  <Area type="monotone" dataKey="Capital brut" stroke="#8b5cf6" strokeWidth={2} fill="url(#gnBrut)"/>
                  <Area type="monotone" dataKey="Emprunts" stroke="#ef4444" strokeWidth={1.5} fill="none" strokeDasharray="5 5"/>
                  <Area type="monotone" dataKey="Capital net" stroke="#10b981" strokeWidth={2} fill="url(#gnNet)"/>
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            <Card>
              <h3 className="text-sm font-semibold text-white mb-4">Indicateurs clés</h3>
              <div className="space-y-4">
                <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,0.03)"}}>
                  <div className="text-xs mb-1" style={{color:"rgba(255,255,255,0.5)"}}>Taux d'endettement</div>
                  <div className="text-lg font-bold text-white">{totals.totalPrincipal>0?(totals.totalLoansCurrent/totals.totalPrincipal*100).toFixed(1):0}%</div>
                  <div className="text-xs" style={{color:"rgba(255,255,255,0.3)"}}>Dette / Capital brut</div>
                </div>
                <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,0.03)"}}>
                  <div className="text-xs mb-1" style={{color:"rgba(255,255,255,0.5)"}}>Couverture des remboursements</div>
                  <div className="text-lg font-bold" style={{color:totals.lastMonthInterest>=totals.totalMonthlyPayments?"#10b981":"#ef4444"}}>
                    {totals.totalMonthlyPayments>0?(totals.lastMonthInterest/totals.totalMonthlyPayments).toFixed(2)+"x":"N/A"}
                  </div>
                  <div className="text-xs" style={{color:"rgba(255,255,255,0.3)"}}>Intérêts / Mensualités</div>
                </div>
                <div className="rounded-xl p-3" style={{background:"rgba(255,255,255,0.03)"}}>
                  <div className="text-xs mb-1" style={{color:"rgba(255,255,255,0.5)"}}>Rendement net après dette</div>
                  <div className="text-lg font-bold" style={{color:totals.netMonthlyIncome>=0?"#10b981":"#ef4444"}}>
                    {totals.totalPrincipal>0?(totals.netMonthlyIncome*12/totals.totalPrincipal*100).toFixed(1):0}% / an
                  </div>
                  <div className="text-xs" style={{color:"rgba(255,255,255,0.3)"}}>(Intérêts - Mensualités) × 12 / Capital</div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* === UPDATE === */}
        {activeTab==="update" && (
          <div className="grid grid-cols-1 gap-4">
            <Card>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-semibold text-white">Gestion des données</h3>
                  <p className="text-xs mt-1" style={{color:"rgba(255,255,255,0.4)"}}>Importez/exportez vos données JSON pour les conserver</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Btn onClick={exportJSON} variant="success">Exporter JSON</Btn>
                  <Btn onClick={()=>fileRef.current?.click()} variant="secondary">Importer JSON</Btn>
                  <input ref={fileRef} type="file" accept=".json" onChange={importJSON} className="hidden"/>
                  <Btn onClick={()=>setShowAddMonth(true)}>+ Nouveau mois</Btn>
                </div>
              </div>
              {showAddMonth && (
                <div className="mt-4 p-4 rounded-xl" style={{background:"rgba(139,92,246,0.08)",border:"1px solid rgba(139,92,246,0.2)"}}>
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <span className="text-xs text-white font-medium">Ajouter : </span>
                      <span className="text-xs font-semibold" style={{color:"#8b5cf6"}}>{fmtMonth(nextMonth(months[months.length-1]))}</span>
                      <span className="text-xs ml-2" style={{color:"rgba(255,255,255,0.4)"}}>(capital et emprunts du mois précédent copiés)</span>
                    </div>
                    <div className="flex gap-2"><Btn onClick={()=>setShowAddMonth(false)} variant="secondary">Annuler</Btn><Btn onClick={addNewMonth}>Confirmer</Btn></div>
                  </div>
                </div>
              )}
            </Card>

            <Card>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                <h3 className="text-sm font-semibold text-white">Mise à jour mensuelle</h3>
                <div className="flex items-center gap-3">
                  <select value={editMonth} onChange={e=>loadMonth(Number(e.target.value))}
                    className="rounded-lg px-3 py-2 text-xs text-white outline-none cursor-pointer"
                    style={{background:"rgba(139,92,246,0.15)",border:"1px solid rgba(139,92,246,0.3)"}}>
                    {months.map((m,i)=><option key={i} value={i} style={{background:"#1a103a"}}>{fmtMonth(m)}</option>)}
                  </select>
                  {!showForm && <Btn onClick={()=>{loadMonth(editMonth);setShowForm(true);}}>Modifier</Btn>}
                </div>
              </div>

              {showForm ? (
                <div>
                  {/* Platforms */}
                  <h4 className="text-xs font-semibold text-white mb-3" style={{color:"rgba(255,255,255,0.6)"}}>Plateformes d'investissement</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                    {platforms.map((p,i)=>(
                      <div key={p} className="rounded-xl p-4" style={{background:"rgba(255,255,255,0.03)",border:"1px solid rgba(255,255,255,0.06)"}}>
                        <div className="flex items-center gap-2 mb-3"><div className="w-3 h-3 rounded-full" style={{background:COLORS[i%COLORS.length]}}/><span className="text-xs font-medium text-white">{p}</span></div>
                        <div className="space-y-2">
                          <div><label className="text-xs block mb-1" style={{color:"rgba(255,255,255,0.4)"}}>Intérêts (€)</label>
                            <input type="number" value={formData[p]?.interest??""} onChange={e=>setFormData(prev=>({...prev,[p]:{...prev[p],interest:e.target.value}}))}
                              className="w-full rounded-lg px-3 py-2 text-xs text-white outline-none" style={{background:"rgba(139,92,246,0.08)",border:"1px solid rgba(139,92,246,0.2)"}} placeholder="0"/></div>
                          <div><label className="text-xs block mb-1" style={{color:"rgba(255,255,255,0.4)"}}>Capital total (€)</label>
                            <input type="number" value={formData[p]?.principal??""} onChange={e=>setFormData(prev=>({...prev,[p]:{...prev[p],principal:e.target.value}}))}
                              className="w-full rounded-lg px-3 py-2 text-xs text-white outline-none" style={{background:"rgba(139,92,246,0.08)",border:"1px solid rgba(139,92,246,0.2)"}} placeholder="0"/></div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Loans */}
                  {loanNames.length>0 && (
                    <>
                      <h4 className="text-xs font-semibold mb-3" style={{color:"rgba(255,255,255,0.6)"}}>Emprunts en cours</h4>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        {loanNames.map((l,i)=>(
                          <div key={l} className="rounded-xl p-4" style={{background:"rgba(239,68,68,0.03)",border:"1px solid rgba(239,68,68,0.1)"}}>
                            <div className="flex items-center gap-2 mb-3"><div className="w-3 h-3 rounded-full" style={{background:LOAN_COLORS[i%LOAN_COLORS.length]}}/><span className="text-xs font-medium text-white">{l}</span></div>
                            <div><label className="text-xs block mb-1" style={{color:"rgba(255,255,255,0.4)"}}>Restant dû (€)</label>
                              <input type="number" value={loanFormData[l]??""} onChange={e=>setLoanFormData(prev=>({...prev,[l]:e.target.value}))}
                                className="w-full rounded-lg px-3 py-2 text-xs text-white outline-none" style={{background:"rgba(239,68,68,0.05)",border:"1px solid rgba(239,68,68,0.15)"}} placeholder="0"/></div>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  <div className="flex gap-3 justify-end">
                    <Btn onClick={()=>setShowForm(false)} variant="secondary">Annuler</Btn>
                    <Btn onClick={saveMonth} variant="success">Sauvegarder</Btn>
                  </div>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr style={{borderBottom:"1px solid rgba(255,255,255,0.06)"}}>
                        <th className="text-left py-2 font-medium" style={{color:"rgba(255,255,255,0.5)"}}>Plateforme</th>
                        <th className="text-right py-2 font-medium" style={{color:"rgba(255,255,255,0.5)"}}>Capital</th>
                        <th className="text-right py-2 font-medium" style={{color:"rgba(255,255,255,0.5)"}}>Intérêts</th>
                        <th className="text-right py-2 font-medium" style={{color:"rgba(255,255,255,0.5)"}}>% du total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {platforms.map((p,i)=>{
                        const cap=principal[p]?.[editMonth]||0,int=interests[p]?.[editMonth]||0;
                        const tc=platforms.reduce((s,pl)=>s+(principal[pl]?.[editMonth]||0),0);
                        return (
                          <tr key={p} style={{borderBottom:"1px solid rgba(255,255,255,0.03)"}}>
                            <td className="py-2.5 flex items-center gap-2"><div className="w-2 h-2 rounded-full" style={{background:COLORS[i%COLORS.length]}}/><span className="text-white">{p}</span></td>
                            <td className="text-right text-white py-2.5">{fmt(cap)}</td>
                            <td className="text-right py-2.5" style={{color:int>0?"#10b981":"rgba(255,255,255,0.3)"}}>{int>0?"+"+fmt(int):"-"}</td>
                            <td className="text-right py-2.5" style={{color:"rgba(255,255,255,0.4)"}}>{tc>0?(cap/tc*100).toFixed(1)+"%":"-"}</td>
                          </tr>
                        );
                      })}
                      <tr style={{borderTop:"1px solid rgba(139,92,246,0.2)"}}>
                        <td className="py-2.5 font-semibold text-white">Total investissements</td>
                        <td className="text-right font-semibold text-white py-2.5">{fmt(platforms.reduce((s,p)=>s+(principal[p]?.[editMonth]||0),0))}</td>
                        <td className="text-right font-semibold py-2.5" style={{color:"#10b981"}}>+{fmt(platforms.reduce((s,p)=>s+(interests[p]?.[editMonth]||0),0))}</td>
                        <td className="text-right font-semibold text-white py-2.5">100%</td>
                      </tr>
                    </tbody>
                  </table>

                  {loanNames.length>0 && (
                    <>
                      <div className="mt-4 mb-2 text-xs font-semibold" style={{color:"rgba(255,255,255,0.5)"}}>Emprunts</div>
                      <table className="w-full text-xs">
                        <tbody>
                          {loanNames.map((l,i)=>{
                            const val=loans[l]?.[editMonth]||0;
                            return (
                              <tr key={l} style={{borderBottom:"1px solid rgba(255,255,255,0.03)"}}>
                                <td className="py-2.5 flex items-center gap-2"><div className="w-2 h-2 rounded-full" style={{background:LOAN_COLORS[i%LOAN_COLORS.length]}}/><span className="text-white">{l}</span></td>
                                <td className="text-right py-2.5" style={{color:"#ef4444"}}>{fmt(val)}</td>
                              </tr>
                            );
                          })}
                          <tr style={{borderTop:"1px solid rgba(239,68,68,0.2)"}}>
                            <td className="py-2.5 font-semibold text-white">Total emprunts</td>
                            <td className="text-right font-semibold py-2.5" style={{color:"#ef4444"}}>{fmt(loanNames.reduce((s,l)=>s+(loans[l]?.[editMonth]||0),0))}</td>
                          </tr>
                          <tr style={{borderTop:"1px solid rgba(139,92,246,0.3)"}}>
                            <td className="py-2.5 font-bold text-white">Capital net</td>
                            <td className="text-right font-bold py-2.5" style={{color:"#10b981"}}>
                              {fmt(platforms.reduce((s,p)=>s+(principal[p]?.[editMonth]||0),0) - loanNames.reduce((s,l)=>s+(loans[l]?.[editMonth]||0),0))}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </>
                  )}
                </div>
              )}
            </Card>
          </div>
        )}

        <div className="text-center mt-8 text-xs" style={{color:"rgba(255,255,255,0.15)"}}>
          Portfolio Dashboard — {months.length} mois de données — Dernier mois : {months.length>0?fmtMonth(months[months.length-1]):""}
        </div>
      </div>
    </div>
  );
}
