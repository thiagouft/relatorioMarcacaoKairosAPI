document.addEventListener('DOMContentLoaded', () => {
    // Funções auxiliares para formatação e conversão de data/hora
    function getFormatDataHoraAtual() {
        const agora = new Date();
        const dia = String(agora.getDate()).padStart(2, '0');
        const mes = String(agora.getMonth() + 1).padStart(2, '0');
        const ano = agora.getFullYear();
        const hora = String(agora.getHours()).padStart(2, '0');
        const minuto = String(agora.getMinutes()).padStart(2, '0');
        return `${dia}/${mes}/${ano} ${hora}:${minuto}`;
    }

    function getFormatDataHoraAtualIso() {
        const agora = new Date();
        const dia = String(agora.getDate()).padStart(2, '0');
        const mes = String(agora.getMonth() + 1).padStart(2, '0');
        const ano = agora.getFullYear();
        const hora = String(agora.getHours()).padStart(2, '0');
        const minuto = String(agora.getMinutes()).padStart(2, '0');
        return `${ano}-${mes}-${dia}T${hora}:${minuto}`;
    }

    function convertBrToIso(dataHoraBr) {
        if (dataHoraBr.includes('T')) {
            return dataHoraBr;
        }
        const regex = /^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})$/;
        const match = dataHoraBr.trim().match(regex);
        if (!match) return null;
        const [_, dia, mes, ano, hora, minuto] = match;
        return `${ano}-${mes}-${dia}T${hora}:${minuto}`;
    }

    // Use the global window variable we set in the template
    const gruposRelogios = window.gruposRelogios || {};

    // Handle tab navigation via hash
    function handleHashChange() {
        const hash = window.location.hash;
        const isDesligamento = hash === '#desligamento';
        const isPonteiro = hash === '#ponteiro';
        const isDataHora = hash === '#datahora';
        const isEnvio = hash === '' || hash === '#envio';

        const panelComandos = document.getElementById('panel-envio-comandos');
        const panelRelogios = document.getElementById('panel-envio-relogios');
        const panelDesligamento = document.getElementById('panel-desligamento');
        const panelPonteiro = document.getElementById('panel-ponteiro');
        const panelDataHora = document.getElementById('panel-datahora');

        if (panelComandos) panelComandos.style.display = isEnvio ? 'block' : 'none';
        if (panelRelogios) panelRelogios.style.display = isDesligamento ? 'none' : 'block';
        if (panelDesligamento) panelDesligamento.style.display = isDesligamento ? 'block' : 'none';
        if (panelPonteiro) panelPonteiro.style.display = isPonteiro ? 'block' : 'none';
        if (panelDataHora) panelDataHora.style.display = isDataHora ? 'block' : 'none';
    }

    window.addEventListener('hashchange', handleHashChange);
    handleHashChange(); // Executar ao carregar a página

    // Set default date for pointer repositioning (yesterday)
    const dateInput = document.getElementById('dataPonteiro');
    if (dateInput) {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const yyyy = yesterday.getFullYear();
        const mm = String(yesterday.getMonth() + 1).padStart(2, '0');
        const dd = String(yesterday.getDate()).padStart(2, '0');
        dateInput.value = `${yyyy}-${mm}-${dd}`;
    }

    // Renderiza os links de download (remove duplicados antes de inserir)
    function renderDownloads(resultDiv, result) {
        // remove se já existir
        const existing = resultDiv.querySelectorAll('.download-section');
        existing.forEach((el) => el.remove());

        const parts = [];
        if (result.sucessoFileName) {
            parts.push(`<a href="/static/${result.sucessoFileName}" target="_blank">📥 Baixar Arquivo de Sucesso</a>`);
        }
        if (result.falhaFileName) {
            parts.push(`<a href="/static/${result.falhaFileName}" target="_blank">📥 Baixar Arquivo de Falhas</a>`);
        }
        if (result.logFileName) {
            parts.push(`<a href="/static/${result.logFileName}" target="_blank">📥 Baixar Log de Falhas</a>`);
        }
        if (parts.length === 0) return;

        const div = document.createElement('div');
        div.className = 'download-section';
        div.innerHTML = '<strong>Arquivos Gerados:</strong>' + parts.join('');
        resultDiv.appendChild(div);
    }

    document.getElementById("uploadForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const fileInput = document.getElementById("arquivo");
        const matriculasInput = document.getElementById("matriculas").value.trim();
        const resultDiv = document.getElementById("result");

        resultDiv.innerHTML = ""; // Limpa os antigos resultados
        resultDiv.style.display = "none";

        const formData = new FormData();
        if (fileInput.files.length > 0) {
            formData.append("arquivo", fileInput.files[0]);
        } else if (matriculasInput.length > 0) {
            const matriculas = matriculasInput
                .split(",")
                .map((m) => m.trim())
                .filter((m) => m !== "");

            if (matriculas.length === 0) {
                alert("Por favor, digite pelo menos uma matrícula válida!");
                return;
            }
            formData.append("matriculas", JSON.stringify(matriculas));
        } else {
            alert("Por favor, selecione um arquivo ou digite as matrículas!");
            return;
        }

        const comandos = {};
        const checkboxesComandos = document.querySelectorAll('input[name="comandos"]:checked');
        if (checkboxesComandos.length === 0) {
            alert("Por favor, selecione pelo menos um comando!");
            return;
        }
        checkboxesComandos.forEach((checkbox) => {
            comandos[checkbox.value] = true;
        });

        const relogios = [];
        const checkboxesRelogios = document.querySelectorAll('input[name="relogios"]:checked');
        if (checkboxesRelogios.length === 0) {
            alert("Por favor, selecione pelo menos um relógio!");
            return;
        }
        checkboxesRelogios.forEach((checkbox) => {
            relogios.push(parseInt(checkbox.value, 10));
        });

        formData.append("comandos", JSON.stringify(comandos));
        formData.append("relogios", JSON.stringify(relogios));

        const progressBar = document.getElementById("progressBar");
        const progressBarInner = progressBar.querySelector(".progress-bar-fill");
        progressBar.style.display = "block";
        progressBarInner.textContent = "Processando...";
        progressBarInner.style.backgroundColor = "#ecc94b"; // yellow while processing

        try {
            const response = await fetch("/api/envio_comando/processar", {
                method: "POST",
                body: formData,
            });

            let result;
            try {
                result = await response.json();
            } catch (e) {
                throw new Error("Resposta do servidor não pôde ser interpretada.");
            }

            if (!response.ok) {
                throw new Error(result.mensagem || "Erro ao processar a requisição no servidor.");
            }

            progressBar.style.display = "none";
            resultDiv.style.display = "block";

            if (result.sucesso) {
                resultDiv.innerHTML = `
                  <p class="success" style="color: #276749; background-color: #c6f6d5; padding: 0.75rem; border-radius: 6px; font-weight: 500;">
                      ✅ ${result.mensagem} <br>
                      <a href="/comandos_agendados" style="color: #2b6cb0; font-weight: 600; text-decoration: underline;">👉 Ver Comandos Agendados</a>
                  </p>
               `;
                showToast("Comando enviado para a fila de execução imediata com sucesso!", "success");
            } else {
                resultDiv.innerHTML = `<p class="error" style="color: #9b2c2c; background-color: #fed7d7; padding: 0.75rem; border-radius: 6px;">❌ ${result.mensagem}</p>`;
            }
        } catch (error) {
            progressBar.style.display = "none";
            resultDiv.style.display = "block";
            resultDiv.innerHTML = `<p class="error">Erro de conexão: ${error.message}</p>`;
        }
    });

    document.getElementById("associarRelogios").addEventListener("click", async () => {
        const fileInput = document.getElementById("arquivo");
        const matriculasInput = document.getElementById("matriculas").value.trim();
        const resultDiv = document.getElementById("result");

        resultDiv.innerHTML = "";
        resultDiv.style.display = "none";

        const formData = new FormData();
        if (fileInput.files.length > 0) {
            formData.append("arquivo", fileInput.files[0]);
        } else if (matriculasInput.length > 0) {
            const matriculas = matriculasInput
                .split(",")
                .map((m) => m.trim())
                .filter((m) => m !== "");
            if (matriculas.length === 0) {
                alert("Por favor, digite pelo menos uma matrícula válida!");
                return;
            }
            formData.append("matriculas", JSON.stringify(matriculas));
        } else {
            alert("Por favor, selecione um arquivo ou digite as matrículas!");
            return;
        }

        const relogiosSelecionados = Array.from(
            document.querySelectorAll('input[name="relogios"]:checked')
        ).map((checkbox) => parseInt(checkbox.value, 10));

        if (relogiosSelecionados.length === 0) {
            alert("Por favor, selecione pelo menos um relógio.");
            return;
        }

        formData.append("relogios", JSON.stringify(relogiosSelecionados));

        const progressBar = document.getElementById("progressBar");
        const progressBarInner = progressBar.querySelector(".progress-bar-fill");
        progressBar.style.display = "block";
        progressBarInner.textContent = "Associando relógios...";
        progressBarInner.style.backgroundColor = "#ecc94b";

        try {
            const response = await fetch("/api/envio_comando/associar", {
                method: "POST",
                body: formData,
            });

            let result;
            try {
                result = await response.json();
            } catch (e) {
                throw new Error("Resposta inválida do servidor.");
            }

            progressBar.style.display = "none";
            resultDiv.style.display = "block";

            if (!response.ok) {
                throw new Error(result.mensagem || "Erro de servidor ao processar.");
            }

            if (result.sucesso) {
                resultDiv.innerHTML = `
                  <p class="success">${result.mensagem}</p>
                  <p class="success">Crachás processados: ${result.detalhes?.crachasProcessados || 0}</p>
              `;
                renderDownloads(resultDiv, result);
                alert("A associação foi concluída! Os arquivos estão prontos para download.");
            } else {
                resultDiv.innerHTML = `<p class="error">${result.mensagem}</p>`;
                renderDownloads(resultDiv, result);
            }
        } catch (error) {
            progressBar.style.display = "none";
            resultDiv.style.display = "block";
            resultDiv.innerHTML = `<p class="error">Erro de conexão: ${error.message}</p>`;
        }
    });

    // Lógica para o botão Agendar Comando em Envio de Comando
    const btnAgendarModal = document.getElementById("agendarEnvioComando");
    const modalAgendamento = document.getElementById("modalAgendamento");
    const btnCancelarModal = document.getElementById("cancelarModalAgendamento");
    const btnConfirmarModal = document.getElementById("confirmarModalAgendamento");
    const inputDataHoraModal = document.getElementById("dataHoraModal");

    if (btnAgendarModal && modalAgendamento) {
        btnAgendarModal.addEventListener("click", () => {
            const fileInput = document.getElementById("arquivo");
            const matriculasInput = document.getElementById("matriculas").value.trim();

            if (fileInput.files.length === 0 && matriculasInput.length === 0) {
                alert("Por favor, selecione um arquivo ou digite as matrículas antes de agendar!");
                return;
            }

            const checkboxesComandos = document.querySelectorAll('input[name="comandos"]:checked');
            if (checkboxesComandos.length === 0) {
                alert("Por favor, selecione pelo menos um comando!");
                return;
            }

            const checkboxesRelogios = document.querySelectorAll('input[name="relogios"]:checked');
            if (checkboxesRelogios.length === 0) {
                alert("Por favor, selecione pelo menos um relógio!");
                return;
            }

            modalAgendamento.style.display = "flex";
            if (inputDataHoraModal) {
                inputDataHoraModal.value = getFormatDataHoraAtualIso();
            }
        });

        if (btnCancelarModal) {
            btnCancelarModal.addEventListener("click", () => {
                modalAgendamento.style.display = "none";
            });
        }

        if (btnConfirmarModal) {
            btnConfirmarModal.addEventListener("click", async () => {
                const dataHoraValBr = document.getElementById("dataHoraModal").value.trim();
                if (!dataHoraValBr) {
                    alert("Por favor, digite a data e hora para o agendamento!");
                    return;
                }

                const dataHoraVal = convertBrToIso(dataHoraValBr);
                if (!dataHoraVal) {
                    alert("Formato de data e hora inválido! Por favor, use o formato DD/MM/AAAA HH:MM (ex: 31/07/2026 09:40).");
                    return;
                }

                const fileInput = document.getElementById("arquivo");
                const matriculasInput = document.getElementById("matriculas").value.trim();
                const resultDiv = document.getElementById("result");

                const formData = new FormData();
                formData.append("data_hora_execucao", dataHoraVal);

                if (fileInput.files.length > 0) {
                    formData.append("arquivo", fileInput.files[0]);
                } else if (matriculasInput.length > 0) {
                    const matriculas = matriculasInput
                        .split(",")
                        .map((m) => m.trim())
                        .filter((m) => m !== "");
                    formData.append("matriculas", JSON.stringify(matriculas));
                }

                const comandos = {};
                document.querySelectorAll('input[name="comandos"]:checked').forEach((cb) => {
                    comandos[cb.value] = true;
                });
                formData.append("comandos", JSON.stringify(comandos));

                const relogios = [];
                document.querySelectorAll('input[name="relogios"]:checked').forEach((cb) => {
                    relogios.push(parseInt(cb.value, 10));
                });
                formData.append("relogios", JSON.stringify(relogios));

                btnConfirmarModal.disabled = true;
                btnConfirmarModal.textContent = "Salvando...";

                try {
                    const response = await fetch("/api/agendamento_comandos/criar", {
                        method: "POST",
                        body: formData,
                    });

                    const res = await response.json();
                    modalAgendamento.style.display = "none";
                    resultDiv.style.display = "block";

                    if (res.sucesso) {
                        resultDiv.innerHTML = `
                            <p class="success" style="color: #276749; background-color: #c6f6d5; padding: 0.75rem; border-radius: 6px; font-weight: 500;">
                                ✅ ${res.mensagem} <br>
                                <a href="/comandos_agendados" style="color: #2b6cb0; font-weight: 600; text-decoration: underline;">👉 Ver Comandos Agendados</a>
                            </p>
                        `;
                        alert("Agendamento criado com sucesso!");
                    } else {
                        resultDiv.innerHTML = `<p class="error" style="color: #9b2c2c; background-color: #fed7d7; padding: 0.75rem; border-radius: 6px;">❌ ${res.mensagem}</p>`;
                    }
                } catch (err) {
                    modalAgendamento.style.display = "none";
                    resultDiv.style.display = "block";
                    resultDiv.innerHTML = `<p class="error">Erro ao agendar: ${err.message}</p>`;
                } finally {
                    btnConfirmarModal.disabled = false;
                    btnConfirmarModal.textContent = "Confirmar Agendamento";
                }
            });
        }
    }

    async function fetchRelogios() {
        const relogiosDiv = document.getElementById("relogios");
        relogiosDiv.innerHTML = "<em>Carregando relógios...</em>";

        try {
            const response = await fetch("/api/envio_comando/relogios");
            if (!response.ok) throw new Error("Falha ao buscar relógios.");
            const relogios = await response.json();

            relogiosDiv.innerHTML = "";

            // Adiciona checkboxes de grupos acima dos relógios
            const gruposDiv = document.createElement("div");
            gruposDiv.className = "grupos-relogios";

            Object.entries(gruposRelogios).forEach(([grupo, ids]) => {
                const label = document.createElement("label");
                label.style.fontWeight = "bold";
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.className = "grupo-relogio-checkbox";
                checkbox.dataset.grupo = grupo;

                label.appendChild(checkbox);
                label.appendChild(document.createTextNode(` Selecionar grupo: ${grupo}`));
                gruposDiv.appendChild(label);

                // Lógica de seleção/desseleção do grupo
                checkbox.addEventListener("change", function () {
                    relogios.forEach((relogio) => {
                        if (ids.includes(relogio.RelogioNumero)) {
                            const cb = relogiosDiv.querySelector(
                                `input[name='relogios'][value='${relogio.RelogioNumero}']`
                            );
                            if (cb) cb.checked = this.checked;
                        }
                    });
                });
            });

            relogiosDiv.parentNode.insertBefore(gruposDiv, relogiosDiv);

            // Renderiza os relógios normalmente
            relogios.forEach((relogio) => {
                const label = document.createElement("label");
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.name = "relogios";
                checkbox.value = relogio.RelogioNumero;

                label.appendChild(checkbox);
                label.appendChild(
                    document.createTextNode(` ${relogio.RelogioNumero} - ${relogio.RelogioNome}`)
                );
                relogiosDiv.appendChild(label);
            });
        } catch (error) {
            console.error("Erro ao buscar relógios:", error);
            relogiosDiv.innerHTML = `<span class="error">Falha ao carregar a lista de relógios. Verifique a conexão.</span>`;
        }
    }

    document.getElementById("selectAllRelogios").addEventListener("click", () => {
        const checkboxes = document.querySelectorAll('input[name="relogios"]');
        checkboxes.forEach((checkbox) => {
            checkbox.checked = true;
        });
    });

    document.getElementById("deselectAllRelogios").addEventListener("click", () => {
        const checkboxes = document.querySelectorAll('input[name="relogios"]');
        checkboxes.forEach((checkbox) => {
            checkbox.checked = false;
        });
        // Também limpa os checkboxes dos grupos de relógios
        const grupoCheckboxes = document.querySelectorAll('.grupo-relogio-checkbox');
        grupoCheckboxes.forEach((cb) => {
            cb.checked = false;
        });
    });

    // Call the fetch relógios API
    fetchRelogios();

    document.getElementById("desligamentoForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const fileInput = document.getElementById("arquivoDesligamento");
        const resultDiv = document.getElementById("resultDesligamento");

        resultDiv.innerHTML = "";
        resultDiv.style.display = "none";

        const formData = new FormData();
        if (!fileInput.files[0]) {
            alert("Por favor, selecione um arquivo para desligamento!");
            return;
        }
        formData.append("arquivo", fileInput.files[0]);

        const progressBar = document.getElementById("progressBarDesligamento");
        const progressBarInner = progressBar.querySelector(".progress-bar-fill");
        progressBar.style.display = "block";
        progressBarInner.textContent = "Processando Desligamento...";
        progressBarInner.style.backgroundColor = "#e53e3e"; // Red theme for dismiss

        try {
            const response = await fetch("/api/envio_comando/desligar", {
                method: "POST",
                body: formData,
            });

            let result;
            try {
                result = await response.json();
            } catch (e) {
                throw new Error("Erro de parse na resposta do servidor.");
            }

            if (!response.ok) {
                throw new Error(result.mensagem || "Erro na requisição.");
            }

            progressBar.style.display = "none";
            resultDiv.style.display = "block";

            if (result.sucesso) {
                resultDiv.innerHTML = `
                  <p class="success">${result.mensagem}</p>
                  <p class="success">Funcionários processados: ${result.processados}</p>
              `;
                renderDownloads(resultDiv, result);
                if (result.sucessoFileName || result.falhaFileName) {
                    alert("O processamento foi concluído! Os arquivos estão prontos para download.");
                }
            } else {
                resultDiv.innerHTML = `<p class="error">${result.mensagem}</p>`;
                renderDownloads(resultDiv, result);
            }
        } catch (error) {
            progressBar.style.display = "none";
            resultDiv.style.display = "block";
            resultDiv.innerHTML = `<p class="error">Erro de conexão: ${error.message}</p>`;
        }
    });

    // Reposição de Ponteiro Form Submit Handler (SSE Streaming)
    const ponteiroForm = document.getElementById('ponteiroForm');
    if (ponteiroForm) {
        ponteiroForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const dateVal = document.getElementById('dataPonteiro').value;
            
            const selectedClocks = Array.from(
                document.querySelectorAll('input[name="relogios"]:checked')
            ).map(cb => parseInt(cb.value, 10));

            if (selectedClocks.length === 0) {
                alert("Por favor, selecione pelo menos um relógio.");
                return;
            }

            const consoleDiv = document.getElementById('consolePonteiro');
            const logContent = document.getElementById('logContentPonteiro');
            const cancelBtn = document.getElementById('cancelPonteiro');
            
            consoleDiv.style.display = 'block';
            logContent.innerHTML = '⏳ Conectando ao servidor para iniciar reposição de ponteiro...\n';
            if (cancelBtn) cancelBtn.style.display = 'block';

            const btn = e.target.querySelector('button[type="submit"]');
            btn.disabled = true;
            btn.textContent = 'Processando Reposição...';

            const relogiosParam = encodeURIComponent(JSON.stringify(selectedClocks));
            const url = `/api/automacao/stream?tipo=ponteiro&data=${dateVal}&relogios=${relogiosParam}`;
            let eventSource = new EventSource(url);

            const cleanUp = () => {
                if (eventSource) {
                    eventSource.close();
                    eventSource = null;
                }
                btn.disabled = false;
                btn.textContent = 'Iniciar Reposição de Ponteiro';
                if (cancelBtn) cancelBtn.style.display = 'none';
            };

            if (cancelBtn) {
                cancelBtn.onclick = () => {
                    logContent.innerHTML += '❌ Operação cancelada pelo usuário.\n';
                    logContent.scrollTop = logContent.scrollHeight;
                    cleanUp();
                };
            }

            eventSource.onmessage = function(event) {
                logContent.innerHTML += event.data + '\n';
                logContent.scrollTop = logContent.scrollHeight;
                
                if (event.data.includes('🏁 Automação') || event.data.includes('❌ Erro') || event.data.includes('🔒 Navegador encerrado.')) {
                    cleanUp();
                }
            };

            eventSource.onerror = function(err) {
                logContent.innerHTML += '❌ Erro na conexão com o servidor ou processo abortado.\n';
                logContent.scrollTop = logContent.scrollHeight;
                cleanUp();
            };
        });
    }

    // Data e Hora Form Submit Handler (SSE Streaming)
    const datahoraForm = document.getElementById('datahoraForm');
    if (datahoraForm) {
        datahoraForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const selectedClocks = Array.from(
                document.querySelectorAll('input[name="relogios"]:checked')
            ).map(cb => parseInt(cb.value, 10));

            if (selectedClocks.length === 0) {
                alert("Por favor, selecione pelo menos um relógio.");
                return;
            }

            const consoleDiv = document.getElementById('consoleDataHora');
            const logContent = document.getElementById('logContentDataHora');
            const cancelBtn = document.getElementById('cancelDataHora');

            consoleDiv.style.display = 'block';
            logContent.innerHTML = '⏳ Conectando ao servidor para iniciar envio de data e hora...\n';
            if (cancelBtn) cancelBtn.style.display = 'block';

            const btn = e.target.querySelector('button[type="submit"]');
            btn.disabled = true;
            btn.textContent = 'Enviando Data e Hora...';

            const relogiosParam = encodeURIComponent(JSON.stringify(selectedClocks));
            const url = `/api/automacao/stream?tipo=datahora&relogios=${relogiosParam}`;
            let eventSource = new EventSource(url);

            const cleanUp = () => {
                if (eventSource) {
                    eventSource.close();
                    eventSource = null;
                }
                btn.disabled = false;
                btn.textContent = 'Iniciar Envio de Data e Hora';
                if (cancelBtn) cancelBtn.style.display = 'none';
            };

            if (cancelBtn) {
                cancelBtn.onclick = () => {
                    logContent.innerHTML += '❌ Operação cancelada pelo usuário.\n';
                    logContent.scrollTop = logContent.scrollHeight;
                    cleanUp();
                };
            }

            eventSource.onmessage = function(event) {
                logContent.innerHTML += event.data + '\n';
                logContent.scrollTop = logContent.scrollHeight;
                
                if (event.data.includes('🏁 Automação') || event.data.includes('❌ Erro') || event.data.includes('🔒 Navegador encerrado.')) {
                    cleanUp();
                }
            };

            eventSource.onerror = function(err) {
                logContent.innerHTML += '❌ Erro na conexão com o servidor ou processo abortado.\n';
                logContent.scrollTop = logContent.scrollHeight;
                cleanUp();
            };
        });
    }

});
