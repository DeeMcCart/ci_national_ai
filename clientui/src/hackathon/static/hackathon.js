
class Alerts {
    constructor() {
        this.messages = [];
    }

    error(text) {
        this.messages.push(text);
        setTimeout(() => {this.remove(text)}, 3000);
    }

    remove(text) {
        this.messages.splice(this.messages.indexOf(text), 1);
        turtlegui.reload();
    }

    has_message() {
        return this.messages.length > 0;
    }
}

var alerts = new Alerts();


class HackathonUI {
    constructor() {
        this.tab = 'info';
        this.visibility = {
            user_info: false,
            instructions: false,
            disclaimer: false,
        };
        this.user_info = {
            location: null,
            income: null,
            savings: null,
            tax_2023: null,
            tax_2022: null,
            tax_2021: null,
            tax_2020: null,
        };
        this.history = [{
            from: "bot",
            text: "Hallo! Can I help you with your inquiry?"
        }];
        this.valid_prompt = false;
        this.current_prompt = '';
        this.loading = false;
    }

    set_tab(tab_id) {
        this.tab = tab_id;
        turtlegui.reload();
    }

    check_valid_prompt() {
        if(!this.has_prompt() || this.loading) {
            this.valid_prompt = false;
        } else {
            this.valid_prompt = true;
        }
        turtlegui.reload(document.getElementById('send_chat'));
        return this.valid_prompt;
    }

    has_prompt() {
        return this.current_prompt != null && !this.loading;
    }

    check_input(event){
        if(event.key.length == 1) {
            this.current_prompt += event.key;
            this.check_valid_prompt();
        } else if(event.key == 'Enter') {
            this.process_prompt();
        }
    }

    async process_prompt() {
        this.history.push({
            from: "user",
            text: this.current_prompt
        });
        this.loading = true;
        this.valid_prompt = false;
        turtlegui.reload();

        var response = await this.send_prompt();

        this.history.push({
            from: "bot",
            text: response['reply']
        });
        this.loading = false;
        this.current_prompt = '';
        this.valid_prompt = false;
        turtlegui.reload();
    }

    async send_prompt() {
        try {
            var response = await fetch('/clientui/api/chat', {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "prompt": this.current_prompt,
                    "history": this.history,
                    "user_info": this.user_info,
                })
            });
            var data = await response.json();
            return data;
        } catch(error) {
            console.log('Error fetching chat: ', error);
            alerts.error(error);
            return {"reply": "Apologies I experienced an error, could you restate your request?"}
        } finally {
            this.loading = false;
            turtlegui.reload();
        }
    }

    toggle_visible(section){
        this.visibility[section] = !this.visibility[section];
        turtlegui.reload();
    }

    start_chat() {
        this.chat_active = true;
        this.current_prompt = null;
        turtlegui.reload();
    }
}


var hackathon = new HackathonUI();


document.addEventListener("DOMContentLoaded", function(){
    console.log('loaded');
    turtlegui.reload();    
});
