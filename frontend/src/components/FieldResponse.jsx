export default function FieldResponse({ result }) {
  if (!result) {
    return null;
  }

  return (
    <section className="prevention-panel glass">
      <div className="section-head">
        <span>07 / FIELD RESPONSE</span>

        <b>RECOMMENDED ACTIONS</b>
      </div>

      <div className="response-content">
        <div className="response-copy">
          <h3>Preventive protocol</h3>

          <p>
            {result.expert_review
              ? "Expert review has been requested. Use the recommendations below while the agricultural specialist validates the diagnosis."
              : "Current diagnosis does not require expert escalation."}
          </p>
        </div>

        <div className="actions">
          {result.prevention?.length ? result.prevention.map((item, index) => (
            <div key={`${item}-${index}`}>
              <span>
                {String(index + 1).padStart(2, "0")}
              </span>

              {item}
            </div>
          )) : <div>Monitor the crop and consult a local agricultural specialist for next steps.</div>}
        </div>
      </div>
    </section>
  );
}
