package com.example.ragchatbot;

import com.example.ragchatbot.document.entity.Document;
import com.example.ragchatbot.document.repository.DocumentRepository;
import com.example.ragchatbot.user.repository.UserRepository;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class RagChatbotApplicationTests {
    static MockWebServer ragApi;
    @Autowired MockMvc mvc;
    @Autowired UserRepository users;
    @Autowired PasswordEncoder encoder;
    @Autowired DocumentRepository documents;

    @BeforeAll
    static void startServer() throws Exception {
        ragApi = new MockWebServer();
        ragApi.start(18080);
    }

    @AfterAll
    static void stopServer() throws Exception {
        ragApi.shutdown();
    }

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        registry.add("rag.api.url", () -> "http://localhost:18080");
    }

    @Test void authRegisterAndLoginReturnsJwt() throws Exception {
        mvc.perform(post("/api/auth/register").contentType(MediaType.APPLICATION_JSON).content("{\"email\":\"auth@test.com\",\"password\":\"password\",\"fullName\":\"Auth User\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.token", not(emptyString())));
        mvc.perform(post("/api/auth/login").contentType(MediaType.APPLICATION_JSON).content("{\"email\":\"auth@test.com\",\"password\":\"password\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.token", not(emptyString())));
    }

    @Test void uploadDocumentEndpointCallsRagAndCompletes() throws Exception {
        ragApi.enqueue(
            new MockResponse()
                .setHeader("Content-Type", "application/json")
                .setBody(
                    "{\"document_id\":\"doc\",\"status\":\"completed\",\"total_pages\":10,"
                        + "\"total_chunks\":22,\"chunk_report_path\":\"/debug/chunk.json\",\"chunks\":[]}"
                )
        );
        String token = registerAndToken("upload@test.com");
        MockMultipartFile pdf = new MockMultipartFile("file", "sample.pdf", "application/pdf", "%PDF-1.4 test".getBytes(StandardCharsets.UTF_8));
        mvc.perform(multipart("/api/documents/upload").file(pdf).header("Authorization", "Bearer " + token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("completed")).andExpect(jsonPath("$.totalChunks").value(22));
    }

    @Test void uploadDocumentPreservesUnicodeFilenameAndFailedRagReason() throws Exception {
        ragApi.enqueue(
            new MockResponse()
                .setHeader("Content-Type", "application/json")
                .setBody(
                    "{\"document_id\":\"doc\",\"status\":\"failed\",\"total_pages\":3,\"total_chunks\":0,"
                        + "\"chunk_report_path\":\"/debug/chunk.json\",\"extracted_text_length\":0,"
                        + "\"parser_used\":\"pymupdf\",\"error_message\":\"PDF scan/image-only: no text layer found; OCR is required.\",\"chunks\":[]}"
                )
        );
        String token = registerAndToken("unicode-upload@test.com");
        MockMultipartFile pdf = new MockMultipartFile("file", "SÁCH PHONG THỦY ỨNG DỤNG.pdf", "application/pdf", "%PDF-1.4 test".getBytes(StandardCharsets.UTF_8));
        mvc.perform(multipart("/api/documents/upload").file(pdf).header("Authorization", "Bearer " + token))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("failed"))
            .andExpect(jsonPath("$.totalPages").value(3))
            .andExpect(jsonPath("$.originalFileName").value("SÁCH PHONG THỦY ỨNG DỤNG.pdf"))
            .andExpect(jsonPath("$.fileName", containsString("SÁCH PHONG THỦY ỨNG DỤNG.pdf")))
            .andExpect(jsonPath("$.errorMessage", containsString("OCR is required")));
    }

    @Test void chatAskEndpointPersistsAssistantMessage() throws Exception {
        ragApi.enqueue(
            new MockResponse()
                .setHeader("Content-Type", "application/json")
                .setBody(
                    "{\"answer\":\"Chiến thắng Bạch Đằng năm 938 do Ngô Quyền lãnh đạo.\",\"confidence\":0.91,"
                        + "\"sources\":[{\"chunk_id\":\"c1\",\"file_name\":\"doc.pdf\",\"page_start\":1,\"page_end\":1,\"score\":0.91,\"support_level\":\"strong\"}],"
                        + "\"warning\":null,\"retrieval_report_path\":\"/debug/r.json\",\"answer_report_path\":\"/debug/a.json\"}"
                )
        );
        String token = registerAndToken("chat@test.com");
        Document doc = ownedDocument(tokenUser("chat@test.com"));
        String session = mvc
            .perform(
                post("/api/chat/sessions")
                    .header("Authorization", "Bearer " + token)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{\"documentId\":\"" + doc.id + "\",\"title\":\"Test\"}")
            )
            .andExpect(status().isOk())
            .andReturn()
            .getResponse()
            .getContentAsString()
            .split("\"id\":\"")[1]
            .split("\"")[0];
        mvc.perform(
                post("/api/chat/ask")
                    .header("Authorization", "Bearer " + token)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{\"sessionId\":\"" + session + "\",\"documentId\":\"" + doc.id + "\",\"question\":\"Ai lãnh đạo Bạch Đằng 938?\"}")
            )
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.answer.answer", containsString("Ngô Quyền")))
            .andExpect(jsonPath("$.assistant_message.confidence").value(0.91));
    }

    @Test void userOwnershipSecurityBlocksOtherUsersDocument() throws Exception {
        String ownerToken = registerAndToken("owner@test.com");
        String attackerToken = registerAndToken("attacker@test.com");
        Document doc = ownedDocument(tokenUser("owner@test.com"));
        mvc.perform(
                post("/api/chat/sessions")
                    .header("Authorization", "Bearer " + attackerToken)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{\"documentId\":\"" + doc.id + "\",\"title\":\"Forbidden\"}")
            )
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.errorCode").value("NOT_FOUND"));
    }

    private String registerAndToken(String email) throws Exception {
        String body = mvc
            .perform(
                post("/api/auth/register")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content("{\"email\":\"" + email + "\",\"password\":\"password\",\"fullName\":\"Test\"}")
            )
            .andExpect(status().isOk())
            .andReturn()
            .getResponse()
            .getContentAsString();
        return body.split("\"token\":\"")[1].split("\"")[0];
    }

    private UUID tokenUser(String email) { return users.findByEmail(email).orElseThrow().id; }

    private Document ownedDocument(UUID userId) {
        Document doc = new Document();
        doc.userId = userId;
        doc.fileName = UUID.randomUUID() + ".pdf";
        doc.originalFileName = "doc.pdf";
        doc.filePath = "/tmp/doc.pdf";
        doc.status = "completed";
        doc.totalPages = 1;
        doc.totalChunks = 1;
        return documents.save(doc);
    }
}
