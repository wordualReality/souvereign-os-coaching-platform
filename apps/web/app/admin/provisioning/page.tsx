const steps = ['Create client profile','Assign coach','Set commercial gate','Assign journey or cohort','Send invite','Request Core access','Materialize delivery plan','Verify first login'];
export default function ManualProvisioningPage() {
  return <main><h1>Manual Client Provisioning</h1><ol>{steps.map(s => <li key={s}>{s}</li>)}</ol></main>;
}
