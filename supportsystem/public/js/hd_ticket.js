frappe.ui.form.on("HD Ticket", {
	refresh(frm) {

        frm.add_custom_button(__('Go to Client System'), function() {

            const generatedUrl = generateOAuth2Link(frm.doc.custom_client_url, frm.doc.custom_reference_ticket_token);
            window.open(generatedUrl, '_blank');
            
        });
          if (!frm.doc.custom_ticket_timeline || frm.doc.custom_ticket_timeline.length === 0) return;
          render_timeline_graph(frm);
	},
    validate(frm){

        if (!frm.doc.custom_app_name && frm.doc.custom_client_url) {

            frappe.db.get_value('Customer', { website: frm.doc.custom_client_url }, 'customer_name')
                .then(r => {
                    if (r && r.message && r.message.customer_name) {
                        frm.db.set_value('custom_app_name', r.message.customer_name);
                    }
                });
        }
    },
    custom_post_to_git: function (frm) { 
        frappe.call({ 
            method: 'supportsystem.supportsystem.custom.custom_api.trigger_n8n_webhook', 
            args: { 
                title: frm.doc.subject, 
                description: frm.doc.description 
            }, 
            callback: function (r) { 
                if (r.message) { 
                    frappe.msgprint(__('Issue posted successfully: ')); 
                } 
            } 
        }); 
    },
    custom_video_recording: function(frm) {
      frappe.db.get_value("File", {
        attached_to_doctype: frm.doctype,
        attached_to_name: frm.doc.name
      }, "file_url").then((r) => {
        if (r && r.message && r.message.file_url) {
          const file_url = r.message.file_url;
    
          let dialog = new frappe.ui.Dialog({
            title: 'View Recording',
            size: 'large', // can also be 'large' or 'extra-large'
            primary_action_label: 'Close',
            primary_action() {
              dialog.hide();
            }
          });
    
          dialog.$body.html(`
            <video width="100%" controls>
              <source src="${file_url}" type="video/mp4">
              Your browser does not support the video tag.
            </video>
          `);
    
          dialog.show();
    
        } else {
          frappe.msgprint("No video file found.");
        }
      });
    },
    onload(frm){
        frappe.db.get_value("File", {
          attached_to_doctype: frm.doctype,
          attached_to_name: frm.doc.name
        }, "file_url").then((r) => {
          if (r && r.message && r.message.file_url) {
            frm.set_df_property('custom_video_recording', 'hidden', '0');
            
          }
        });
        if (frm.doc.category) {
          const category_key = frappe.scrub(frm.doc.category); // Converts "Doubt" -> "doubt"
    
          frm.set_query("status", function () {
            console.log("Category Key: ", category_key);
              return {
                  filters: {
                      [category_key]: 1
                  }
              };
            });
          }
      }
});





function generateOAuth2Link(url, token) {

    const state = { 
        site: url,
        token: token,
        redirect_to: null
    };
    const encodedState = btoa(JSON.stringify(state));

    const params = new URLSearchParams({
        redirect_uri: `${url}/api/method/frappe.integrations.oauth2_logins.login_via_frappe`,
        state: encodedState,
        response_type: "code",
        scope: "openid",
        client_id: "cav84rjn8k",       // can get_value from the `oauth_client`
    });
    const fullUrl = `http://127.0.0.1:8088/api/method/frappe.integrations.oauth2.authorize?${params.toString()}`;

    return fullUrl;
}

function getStatusColor(status) {
    const colors = {
        "Open": "#e74c3c",
      "Replied": "#f1c40f",
      "Resolved": "#2ecc71",
      "Closed": "#2ecc71",
      "Live": "#2ecc71",
      "Re-Opened": "#e74c3c"
    };
    return colors[status] || "#f1c40f"; // default gray
}

function render_timeline_graph(frm) {
    let timeline = frm.doc.custom_ticket_timeline || [];

    // Sort by timestamp
    timeline.sort((a, b) => {
        return new Date(a.timestamp) - new Date(b.timestamp);
    });

    let html = `<div style="display: flex; align-items: center; flex-wrap: wrap;">`;

    timeline.forEach((row, index) => {
        const color = getStatusColor(row.status);

        // Status box
        html += `
            <div style="display: flex; flex-direction: column; align-items: center; margin: 10px;">
                <div style="padding: 6px 12px; border-radius: 20px; background-color: ${color}; color: white;">
                    ${row.status}
                </div>
                <div style="font-size: 12px; margin-top: 4px;">
                    ${frappe.datetime.str_to_user(row.timestamp.split(" ")[0])}
                </div>
                <div style="font-size: 12px; color: #888;">
                    ${row.added_by}
                </div>
            </div>
        `;

        // Arrow (except after the last one)
        if (index < timeline.length - 1) {
            html += `
            <div style="margin: 0 8px; font-size: 22px; display: flex; align-items: center; height: 100%;">➜</div>            `;
        }
    });

    html += `</div>`;
    frm.fields_dict.custom_timeline_graph.$wrapper.html(html);
}