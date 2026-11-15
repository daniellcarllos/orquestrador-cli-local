export function ComoUsar() {
  return (
    <div className="tela como-usar">
      <section className="cartao">
        <h2>Como usar</h2>
        <ol className="passos">
          <li><b>Configurações:</b> confira se há chave de API (ou use o modo simulado), escolha os modelos de cada nível e preencha os preços.</li>
          <li><b>Nova tarefa:</b> escolha o fluxo, o repositório e os detalhes. Use <b>Ver plano</b> para conferir papéis, modelos e teto sem gastar nada.</li>
          <li><b>Executar:</b> confirme no resumo. A execução roda em segundo plano; você acompanha em <b>Execuções</b>.</li>
          <li><b>Execuções:</b> veja cada agente trabalhando, o custo por etapa e o resultado. Cancele se precisar.</li>
          <li><b>Depois:</b> aplique os patches do desenvolvimento ou envie a revisão para a PR, sempre revisando o texto antes.</li>
        </ol>
      </section>
      <section className="cartao">
        <h2>Qual fluxo usar</h2>
        <table>
          <thead><tr><th>Quero...</th><th>Fluxo</th><th>Custo relativo</th></tr></thead>
          <tbody>
            <tr><td>revisar uma PR ou branch</td><td>Revisar código</td><td>médio: 5 chamadas</td></tr>
            <tr><td>entender um módulo ou responder uma dúvida sobre o código</td><td>Analisar código</td><td>médio: 2 a 10 chamadas</td></tr>
            <tr><td>implementar algo dividido em partes independentes</td><td>Desenvolver em paralelo</td><td>alto: plano + 2 chamadas por subtarefa e rodada</td></tr>
            <tr><td>uma tarefa aberta sem fluxo definido</td><td>Equipe</td><td>variável: o líder decide</td></tr>
            <tr><td>usar a assinatura, sem custo de API</td><td>Terminal</td><td>cota da assinatura</td></tr>
          </tbody>
        </table>
      </section>
      <section className="cartao">
        <h2>Segurança</h2>
        <ul className="passos">
          <li>O painel só abre em 127.0.0.1 e exige o token mostrado pelo <code>serve</code>.</li>
          <li>Os agentes só leem o repositório escolhido, sem shell; segredos são redigidos antes do envio.</li>
          <li>O teto de gasto interrompe a execução; o modo simulado não chama provedor nenhum.</li>
          <li>Patches nunca são aplicados sozinhos; ações em PRs e na biblioteca pedem confirmação, salvo se você marcou execução automática.</li>
        </ul>
      </section>
    </div>
  )
}
